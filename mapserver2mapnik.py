#!/usr/bin/env python

import re
import sys
import mapnik2 as mapnik
import mapscript
import utils

proj = '+init=epsg:4326'
merc = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over'

# colorado
box = "-12197658.2353032,4354107.45296023,-11359191.3507561,5097334.13614237"

postgis = {
    "type":"postgis",
    "dbname":"osm",
    "srid":900913,
    "extent":box,
    "max_size":33
}

remote = {
    "user":"postgres",
    "host":"linux_db_bm",
    "srid":3857,
}

# /benchmarking/wms/2011/data/vector/osm_base_data/data/
#postgis.update(remote)

ms = mapscript.mapObj('../mapserver/osm-google.map')
m = mapnik.Map(800,800,merc)

m.maximum_extent = mapnik.Box2d(*map(float,box.split(',')))
# should be background_color
m.background = utils.ms2color(ms.imagecolor)

layers = []
layer_names = []
layer_ids = []
styles = []
style_cache = {}
#rules = []

pattern = r'([A-Za-z]+)([0-9]+)'

# first collect all unique layers
unique_layers = {}
layer_order = []
data_names = {}

idx1 = 1
for idx in ms.getLayerOrder():
    msl = ms.getLayer(idx)
    base_name = re.findall(pattern,msl.name)[0][0]
    #if not 'road' in base_name:
    #    continue
    
    if not msl.data in data_names:
        layer_name = '%s_%s' % (base_name,idx1)
        data_names[msl.data] = layer_name
        idx1 += 1
    else:
        layer_name = data_names[msl.data]

    rules = []
    casing_rules = []
    text_rules = []
    
    if layer_name in unique_layers:
        rules = unique_layers[layer_name]['rules']
        casing_rules = unique_layers[layer_name]['casing_rules']
        text_rules = unique_layers[layer_name]['text_rules']
    else:
        layer_order.append(layer_name)
        unique_layers[layer_name] = {}
        unique_layers[layer_name]['rules'] = rules
        unique_layers[layer_name]['casing_rules'] = casing_rules
        unique_layers[layer_name]['text_rules'] = text_rules
        unique_layers[layer_name]['data'] = msl.data
        mapnik_layer = utils.ms2layer(msl,layer_name,postgis)
        unique_layers[layer_name]['lyr'] = mapnik_layer

    for idx in range(0,msl.numclasses):
        rule_name = '%s_class%s' %(msl.name,idx)
        msc = msl.getClass(idx)

        # get undercasings - "outlines" in mapserver
        casing_rule = utils.ms2rule(rule_name,ms,msl,msc,casing=True)
        if casing_rule:
            casing_rules.append(casing_rule)

        # get normal strokes and other symbolizers
        rule = utils.ms2rule(rule_name,ms,msl,msc)
        if rule:
            rules.append(rule)
        if hasattr(msl,'labelitem') and msl.labelitem:
            #import pdb;pdb.set_trace()
            text_rules.append(utils.ms2text(rule_name+'_label',msl,msc))

text_layers = []

catch = None#'roads15'

for lay in layer_order:
    layer = unique_layers[lay]['lyr']
    
    hit = False
    
    # under casing
    casing_rules = unique_layers[lay]['casing_rules']
    if len(casing_rules):
        sty = mapnik.Style()
        sty.filter_mode = mapnik.filter_mode.FIRST
        for rule in casing_rules:
            # allow returning whole style for text and casings
            #if isinstance(rule,mapnik.Rule):
            if catch:
                if catch in rule.name:
                   sty.rules.append(rule)
            else:
                sty.rules.append(rule)
        if len(sty.rules):
            hit = True
            sty_name = lay+'_shape_casing'
            m.append_style(sty_name,sty)
            layer.styles.append(sty_name)

    rules = unique_layers[lay]['rules']
    if len(rules):
        sty = mapnik.Style()
        sty.filter_mode = mapnik.filter_mode.FIRST
        for rule in rules:
            # allow returning whole style for text and casings
            #if isinstance(rule,mapnik.Rule):
            if catch:
                if catch in rule.name:
                    sty.rules.append(rule)
            else:
                sty.rules.append(rule)
        if len(sty.rules):
            hit = True
            sty_name = lay+'_shape'
            m.append_style(sty_name,sty)
            layer.styles.append(sty_name)
    
    if hit:
        m.layers.append(layer)

    text_rules = unique_layers[lay]['text_rules']
    if len(text_rules):
        sty = mapnik.Style()
        sty.filter_mode = mapnik.filter_mode.FIRST
        for rule in text_rules:
            # TODO - allow returning whole style for text and casings
            if catch:
                if catch in rule.name:
                    sty.rules.append(rule)
            else:
                sty.rules.append(rule)
        if len(sty.rules):
            hit = True
            sty_name = lay+'_text'
            m.append_style(sty_name,sty)
            text_layer = utils.copy_layer(layer)
            text_layer.styles.append(sty_name)
            text_layers.append(text_layer)

for lay in text_layers:
    m.layers.append(lay)

print mapnik.save_map_to_string(m)
