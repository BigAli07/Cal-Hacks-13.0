"""Replaceable scene consumer. No movement commands are generated."""
import copy
import importlib


class ScenePlugin:
    def __init__(self, specification=None):
        self.adapter = None
        if specification:
            module, factory = specification.split(':', 1)
            self.adapter = getattr(importlib.import_module(module), factory)()
            if not callable(getattr(self.adapter, 'publish', None)) or not callable(getattr(self.adapter, 'close', None)):
                raise ValueError('Hardware adapter must implement publish(scene) and close().')

    def publish(self, scene):
        if self.adapter is None:
            return {'status':'preview_only', 'schema':'pulsepath.scene.v1'}
        try:
            self.adapter.publish(copy.deepcopy(scene))
            return {'status':'delivered_to_adapter', 'schema':'pulsepath.scene.v1',
                    'note':'Delivery does not confirm physical buzzer operation.'}
        except Exception as error:
            return {'status':'adapter_error', 'error':str(error)}

    def close(self):
        if self.adapter:
            self.adapter.close()
