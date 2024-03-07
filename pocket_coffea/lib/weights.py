from dataclasses import dataclass
import inspect
import numpy as np
from collections import defaultdict
from abc import ABC, ABCMeta, abstractmethod
from typing import ClassVar, Callable, Any, List, Union


### Dataclasses to represent the weights to be passed to the WeightsManager
@dataclass
class WeightData:
    name: str
    nominal: np.ndarray
    up: np.ndarray = None
    down: np.ndarray = None

@dataclass
class WeightDataMultiVariation:
    name: str
    nominal: np.ndarray
    variations: List[str]
    up: List[np.ndarray]
    down: List[np.ndarray] = None

### Metaclass to store the dictionary of all the weight classes
class WeightWrapperMeta(ABCMeta):
    # Metaclass to store the dictionary
    # of all the weight classes
    weight_classes = {}
    _lambda_index = 0
    def __new__(metacls, name, bases, clsdict):
        cls = super().__new__(metacls, name, bases, clsdict)
        if name == "WeightLambda":
            return cls
        # Register the class name if it is a subclass of WeightWrapper 
        for base in bases:
            if base.__name__ == "WeightWrapper":
                # only save the subclasses of WeightWrapper
                weight_name = clsdict["name"]
                if weight_name not in metacls.weight_classes:
                    metacls.weight_classes[weight_name] = cls
                else:
                    raise ValueError(f"Weight with name {weight_name} already registered. Please use a different name.")
        return cls


    def wrap_func(cls, name:str,
                  function: Callable[[Any, int, str], Union[WeightData,WeightDataMultiVariation]],
                  has_variations, variations):
        # Create a new class with the compute method
        attrs = {'_function': function,
                 'name': name,
                 'has_variations': has_variations,
                 '__module__': cls.__module__
                 }
        metacls = cls.__class__
        class_name = f"WeightLambda_{metacls._lambda_index+1}"
        new_class = metacls.__new__(metacls, class_name, (cls,), attrs)
        # increase lambda index if successfull
        metacls._lambda_index += 1
        return new_class
  

    
class WeightWrapper(ABC, metaclass=WeightWrapperMeta):
    '''
    Base class creating a schema creating Weights for the analysis.
    The class allows the user to define weights with variations
    that depends on the params and metadata of the specific chunk.
    WeightWrapper instances are passed to the WeightsManager and stored.
    During the processing, the processor object creates a WeightsManager
    object which uses the WeightWrapper object to get the weights.
    In that step, the constructor function is called to customize the
    weights computation depending on the current parameters and chunk metadata
    (like era, year, isMC, isData..).
    The variations are dynamically computed by the WeightWrapper object.
    The variations can be customized by parameters and metadata with the WeightWrapper.
    Doing so different years can have different names for the variations for example. 
    The HistManager will ask the WeightsManager to have the available weights
    variations for the current chunk and will store them in the output file.

    The `name` class attribute is used in the configuration to define the weight.
    The metaclass registration mechanism checks if the user defines more than once
    the same weight class.  
    '''
    name: ClassVar[str] = "base_weight"
    has_variations: ClassVar[bool] = False
         
    
    def __init__(self, params=None, metadata=None):
        self._params = params
        self._metadata = metadata
        self._variations = []

    @abstractmethod
    def compute(self, events, size, shape_variation):
        # setup things for specific year for example
        pass


    @property
    def variations(self):
        return self._variations

    def serialize(self, src_code=False):
        out = {
            "name": self.name,
            "class": {
                "name": self.__class__.__name__,
                "module": self.__class__.__module__,
                "src_file": inspect.getsourcefile(self.__class__),
                "f_hash": hash(self.__class__),
            },
        }
        if src_code: #to be tested
            out["function"]["src_code"] = inspect.getsource(self.__class__)
        return out


class WeightLambda(WeightWrapper):
    '''
    Class to create a weight using a lambda function.
    The lambda function should take as input the parameters and the metadata
    and return a WeightData or WeightDataMultiVariation object.
    The lambda function should be able to handle the variations.
    '''
    # Function that should take [params, metadata, events, size, shape_variationss]
    @property
    @abstractmethod
    def _function(self): #Callable[[Any, Any, Any, int, str], WeightData | WeightDataMultiVariation] = None
        pass

    
    def compute(self, events, size, shape_variation):
        return self._function(self._params, self._metadata, events, size, shape_variation)

 
