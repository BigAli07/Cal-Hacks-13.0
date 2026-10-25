"""Friend's integration starting point: --hardware-plugin example_hardware:create.

publish must return promptly; use bounded queues for slow IO, dropping stale scenes.
Implement a hardware watchdog that turns outputs off after 500 ms without updates.
Unknown distances are None; estimated distances are not verified measurements.
"""
class Adapter:
    def publish(self, scene):
        assert scene['schema_version'] == 'pulsepath.scene.v1'
        for obj in scene['objects']:
            # Replace this with your board's transport. No movement recommendations.
            print({'label':obj['model_label'], 'range_m':obj['distance_m'],
                   'status':obj['distance_status'], 'bearing_deg':obj['horizontal_angle_deg']})

    def close(self):
        # Turn all outputs off and close your board connection here.
        pass


def create():
    return Adapter()
