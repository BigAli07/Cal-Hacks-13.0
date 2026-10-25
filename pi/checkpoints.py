"""Shared checkpoint enrichment for both native and browser demos."""
from haptics import channels_for


def enrich(event, ranges, target='drink can', model_labels=()):
    labels = set(model_labels)
    target_supported = target in labels
    hits = [o for o in event['objects'] if o['model_label']==target]
    event['checkpoints'] = {
        'detection': {'target':target,'supported':target_supported,
                      'status': 'detected' if hits else 'not_detected' if target_supported else 'unsupported_label',
                      'count':len(hits), 'confidence':max((x['confidence'] for x in hits),default=None),
                      'note':'Current frame only. Test obstruction with a real hand; no inferred detections.'},
        'distance':ranges,
    }
    # Marker range is never assigned to arbitrary nearby object boxes.
    event['haptics']={'channels':channels_for(ranges['markers']),
                      'order':['left','centre','right'], 'meaning':'reference_position',
                      'protocol':'P1', 'reference':'marker centre, not object centre'}
    return event
