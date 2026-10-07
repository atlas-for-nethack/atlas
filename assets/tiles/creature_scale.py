"""Shared creature scale for project-original Modern tilesets only.

The catalog owns the tier size and axis. Flat bodies use their longest image
dimension; upright bodies retain their height. Classic
portraits, imported tilesets and upstream artwork do not use this helper.
"""
from PIL import Image


def project_creature(sprite, rule):
    height = rule['height']
    if not isinstance(height, int) or height <= 0:
        raise ValueError('Creature height must be a positive catalog value')
    if sprite.height <= 0 or sprite.width <= 0:
        raise ValueError('Empty creature source')
    axis = rule.get('scaleAxis', 'height')
    if axis not in ('height', 'longest'):
        raise ValueError('Unknown creature scale axis')
    factor = height / (max(sprite.size) if axis == 'longest' else sprite.height)
    width = max(1, round(sprite.width * factor))
    height = max(1, round(sprite.height * factor))
    sprite = sprite.resize((width, height), Image.Resampling.NEAREST)
    anchor = rule['footAnchor']
    return {'image': sprite,
            'offset': [round(anchor[0]*64-width/2), round(anchor[1]*64-height)],
            'depth': round(anchor[1]*64)}
