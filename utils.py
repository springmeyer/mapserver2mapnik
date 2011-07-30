import re
import sys
import mapnik2 as mapnik
import mapscript

merc = '+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +k=1.0 +units=m +nadgrids=@null +wktext +no_defs +over'

box = "-11690811.758434,4826833.1534376,-11687378.549609,4830266.3622626"

p_pattern = r'from (\w+)\W'
t_pattern = r'geometry from \((.*)\)'


postgis = {
    "type":"postgis",
    "dbname":"osm",
    "srid":900913,
    "extent":box
}

def copy_layer(obj):
    lyr = mapnik.Layer(obj.name)
    lyr.abstract = obj.abstract
    lyr.active = obj.active
    lyr.clear_label_cache = obj.clear_label_cache
    lyr.datasource = obj.datasource
    lyr.maxzoom = obj.maxzoom
    lyr.minzoom = obj.minzoom
    lyr.queryable = obj.queryable
    lyr.srs = obj.srs
    lyr.title = obj.title
    return lyr

def ms2color(c):
    #,c.alpha
    return mapnik.Color(c.red,c.green,c.blue)

def ms2text(rule_name,msl,msc):
    rule = mapnik.Rule(rule_name)

    #msl.map.web.minscaledenom
    rule.min_scale =  msl.minscaledenom
    rule.max_scale =  msl.maxscaledenom
    expr = mapnik.Expression("[%s]" % msl.labelitem)
    # todo... parse font list
    mscl = msc.label.color
    color = ms2color(mscl)
    size = 13
    if msc.label.size > 1:
        size = int(msc.label.size * 1.5)
    text = mapnik.TextSymbolizer(expr,'DejaVu Sans Book',size,color)
    if msl.type == mapscript.MS_LAYER_LINE:
        text.label_placement = mapnik.label_placement.LINE_PLACEMENT
        text.minimum_distance = 500
        text.label_spacing = 750
    else:
        text.wrap_width = 15
        text.minimum_distance = 100
    text.avoid_edges = True
    text.halo_radius = msc.label.outlinewidth
    text.halo_color = mapnik.Color('white')
    #text.allow_overlap = True
    rule.symbols.append(text)
    return rule


match_str = ".match('.*%s.*')"
match_str = " = '%s'"
match_num = ""
def ms2expr(msl,msc):
    ms_expr = msc.getExpressionString()
    
    expr = None
    # ack, special case ....
    #if rule_name.startswith("roads14"):
    #    import pdb;pdb.set_trace()
    if ms_expr:
        val_in = False
        if ms_expr.startswith('/'): # a 'a' in value expression
            val_in = True
        # nasty, nasty...
        if ']"="' in ms_expr:
             # ("[bridge]"="1" and "[type]" = "motorway")
             expr = "%s" % (ms_expr.replace('"[','[').replace(']"',']').replace('"',"'"))
        elif ']=' in ms_expr:
             # [tunnel]=0
             expr = "%s" % (ms_expr.replace('(','').replace(')',''))
        elif '|' in ms_expr:
            expr = ''
            items = ms_expr.split('|')
            eitems = []
            for item in items:
                if str(item) == item:
                    if val_in:
                        eitems.append("[%s]%s" % (msl.classitem,match_str % item.replace('/','')))
                    else:
                        eitems.append("[%s] = '%s'" % (msl.classitem,item.replace('/','')))                    
                else:
                    if val_in:
                        eitems.append("[%s].match(.*%s.*)" % (msl.classitem,item.replace('/','')))
                    else:
                        eitems.append("[%s] = %s" % (msl.classitem,item.replace('/','')))
            expr = ' or '.join(eitems)
        else:
            item = ms_expr.replace('/','').replace('\\','').replace("\"","").replace("\'","")
            if str(item) == item:
                if val_in:
                    expr = "[%s]%s" % (msl.classitem,match_str % item)
                else:
                    expr = "[%s] = '%s'" % (msl.classitem,item)
            else:
                expr = "[%s] = %s" % (msl.classitem,item)
    # hack to fix [bridge]='1' which mapserver allows, ick
    if expr and "='1'" in expr:
        expr = expr.replace("'1'","1").replace("'0'","0")
    return expr

def ms2syms(ms,msl,msc):
    syms = []
    for idx1 in range(0,msc.numstyles):
        msty = msc.getStyle(idx1)
        color = ms2color(msty.color)
        #color = mapnik.Color('green')
        #import pdb;pdb.set_trace()
        sym = None
        # enum MS_LAYER_TYPE {MS_LAYER_POINT, MS_LAYER_LINE, MS_LAYER_POLYGON, MS_LAYER_RASTER, MS_LAYER_ANNOTATION, MS_LAYER_QUERY, MS_LAYER_CIRCLE, MS_LAYER_TILEINDEX, MS_LAYER_CHART};
        if msl.type == mapscript.MS_LAYER_POLYGON:
            sym = mapnik.PolygonSymbolizer()
            sym.fill = color
        elif msl.type == mapscript.MS_LAYER_LINE:
            #import pdb;pdb.set_trace()
            if msty.outlinewidth > 0:
                sym = mapnik.LineSymbolizer()
                # custom property to catch layer
                sym.is_casing = True
                sto = mapnik.Stroke()
                color = ms2color(msty.outlinecolor)
                sto.color = color
                sto.linecap = mapnik.line_cap.round
                sto.linjoin = mapnik.line_join.round
                sto.width = msty.width + (msty.outlinewidth * 2.0)
                sym.stroke = sto
                #if not sto.width > 0:
                #    pass # some odd dash trick in mapserver?
                    #import pdb;pdb.set_trace()
                #else:
                #    rule.symbols.append(symo)
            else:
                sym = mapnik.LineSymbolizer()
                sym.is_casing = False
                st = mapnik.Stroke()
                #color = ms2color(msty.outlinecolor)
                color = ms2color(msty.color)
                st.color = color
                st.linecap = mapnik.line_cap.round
                st.linjoin = mapnik.line_join.round
                #if rule_name == "roads5_class1":
                #    import pdb;pdb.set_trace()
                st.width = msty.width
                #st.width = msty.outlinewidth*3
                if msty.patternlength > 0:
                    # hardcode because msty.pattern seems bunk
                    st.add_dash(2,3)
                #TODO - do something with PRIORITY?
                sym.stroke = st
                #if not st.width > 0:
                #    sym = None # don't attach a non-existant line
                #import pdb;pdb.set_trace()
        elif msl.type == mapscript.MS_LAYER_POLYGON:
            sym = mapnik.PointSymbolizer()
            sym.allow_overlap = True
        elif msl.type == mapscript.MS_LAYER_RASTER:
            sym = mapnik.RasterSymbolizer()
        elif msl.type == mapscript.MS_LAYER_ANNOTATION:
            pass # text
        elif msl.type == mapscript.MS_LAYER_QUERY:
            import pdb;pdb.set_trace()
        elif msl.type == mapscript.MS_LAYER_CIRCLE:
            import pdb;pdb.set_trace()
        elif msl.type == mapscript.MS_LAYER_TILEINDEX:
            import pdb;pdb.set_trace()
        elif msl.type == mapscript.MS_LAYER_CHART:
            import pdb;pdb.set_trace()
        else:# msl.type == mapscript.MS_SHAPE_NULL:
            import pdb;pdb.set_trace()
        if sym:
            syms.append(sym)
    return syms

def ms2rule(rule_name,ms,msl,msc,casing=False):
    rule = mapnik.Rule(rule_name)

    #msl.map.web.minscaledenom
    rule.min_scale =  msl.minscaledenom
    rule.max_scale =  msl.maxscaledenom

    expr = ms2expr(msl,msc)
    if expr:
        rule.filter = mapnik.Expression(expr)
    
    #if rule_name == "railways14_class0":
    #    import pdb;pdb.set_trace()
    syms = ms2syms(ms,msl,msc)
    for sym in syms:
        if casing:
            if hasattr(sym,'is_casing') and sym.is_casing:
                rule.symbols.append(sym)
        else:
            if not hasattr(sym,'is_casing') or not sym.is_casing:
                rule.symbols.append(sym)
    if len(rule.symbols) == 0:
        return None
    return rule

        
 
def ms2layer(msl,layer_name):
    srs = msl.getProjection() or merc
    if srs == '+init=epsg:900913':
        srs = merc
    lyr = mapnik.Layer(layer_name,srs)
    
    if msl.connection: # then we assume postgis
        #host=localhost dbname=osm user=postgres password=postgres port=5432
        #DATA "geometry from (select * from osm_places where type in ('country','continent') and name is not NULL order by population asc nulls first) as foo using unique osm_id using srid=900913"
        
        p = postgis.copy()
        geometry_table = re.findall(p_pattern,msl.data)
        if not geometry_table:
            import pdb;pdb.set_trace()
        else:
            geometry_table = geometry_table[0]
        
        if '(' in msl.data: # then subquery
            table = re.findall(t_pattern,msl.data)
            if not table:
                import pdb;pdb.set_trace()
            else:
                table = '(' + table[0] + ') as t'
        else:
            table = geometry_table            
        p['table'] = table
        p['geometry_table']= geometry_table
        # todo - get extent from query
        lyr.datasource = mapnik.PostGIS(**p)
    else: # assume shapefile
        lyr.datasource = mapnik.Shapefile(file=msl.data)
    return lyr


       
