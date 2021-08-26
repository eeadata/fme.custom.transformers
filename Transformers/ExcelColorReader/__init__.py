import colorsys
from datetime import datetime
import fmeobjects
import locale
import os.path
import sys
import shlex
import traceback

_DEBUG = False
_LOAD_OK = False
_LOAD_ERROR = 'load error'

def egg_filepath(pkg):
    file_dirpath = os.path.dirname(os.path.abspath(__file__))
    fp = os.path.normpath(os.path.join(file_dirpath, '{}-py{}.{}.egg'.format(pkg,sys.version_info.major, sys.version_info.minor)))
    if not os.path.exists(fp): raise Exception('file not found "{}"'.format(fp))
    return fp
try:
  sys.path.extend(map(egg_filepath, ['jdcal-1.3', 'et_xmlfile-1.0.1', 'openpyxl-2.5.0a2']))
  _LOAD_OK = True
except Exception as e:
  _LOAD_ERROR = 'Some python libraries needed for the ExcelColorReader were not loaded.\n{}'.format(str(e))
  sys.stderr.write('WARN: {}\n'.format(_LOAD_ERROR))

def hex_to_rgb(value):
    """Return (red, green, blue) for the color given as #rrggbb."""
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

def get_lum(lum,tint):
    '''http://ciintelligence.blogspot.se/2012/02/converting-excel-theme-color-and-tint.html'''
    if tint < 0:
        return lum * (1.0 + tint)
    return lum * (1.0 - tint) + (1.0 - 1.0 * (1.0 - tint))

def get_theme_colors(wb):
    import xml.etree.ElementTree as ET
    ns = {'drw': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
    root = ET.fromstring(wb.loaded_theme)
    themeEl = root.find('drw:themeElements', ns)
    colorSchemes = themeEl.findall('drw:clrScheme', ns)
    firstColorScheme = colorSchemes[0]
    colors = []
    for c in ['lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6']:
        accent = firstColorScheme.find('drw:{}'.format(c), ns)
        if accent is None: continue
        if 'window' in accent.getchildren()[0].attrib['val']:
            colors.append(accent.getchildren()[0].attrib['lastClr'])
        else:
            colors.append(accent.getchildren()[0].attrib['val'])
    return colors

def evaluate_color(color, theme_colors):
    if color.type =='rgb' and color.rgb[:2] != '00':
        return hex_to_rgb(color.rgb[2:])
    elif color.type == 'theme' and color.theme < len(theme_colors) and color.theme >= 0:
        rgb = [float(x)/255 for x in hex_to_rgb(theme_colors[color.theme])]
        h, l, s = colorsys.rgb_to_hls(*rgb)
        tinted = (h, get_lum(l, color.tint), s)
        return [int(x*255) for x in colorsys.hls_to_rgb(*tinted)]
    return None

class ColorReader(object):
    def __init__(self):
        self._logprefix = 'ExcelColorReader'
        self._session = fmeobjects.FMESession()
        self._logfile = fmeobjects.FMELogFile()
        self._enc = locale.getdefaultlocale()[1]
        self.info('Transformer initiated')
    def _parse_value(self, val, feature):
        if val.startswith('@Evaluate'):
            val = feature.performFunction(val)
        return self._session.decodeFromFMEParsableText(val) 
    def _log_msg(self, msg, level):
        if isinstance(msg, unicode):
            msg = u'{}: {}'.format(self._logprefix, msg).encode(self._enc)
        else:
            msg = u'{}: {}'.format(self._logprefix, unicode(msg)).encode(self._enc)
        self._logfile.logMessageString(msg, level)
    def info(self, msg):
        self._log_msg(msg, fmeobjects.FME_INFORM)
    def debug(self, msg):
        if not _DEBUG: return
        self._log_msg(msg, fmeobjects.FME_WARN)
    def warn(self, msg):
        self._log_msg(msg, fmeobjects.FME_WARN)
    def error(self, msg):
        self._log_msg(msg, fmeobjects.FME_ERROR)
    def input(self, feature):
        dataset, strategy, tablelist, transformername = (self._parse_value(feature.getAttribute(s), feature) for s in ['_excelcolorreader_dataset','_excelcolorreader_strategy','_excelcolorreader_tablelist','_excelcolorreader_transformername'])
        # splitting the supplied value into a list using shlex
        tablelist = [s.decode('utf8') for s in shlex.split(tablelist.encode('utf8'))]
        self._logprefix = transformername
        feature.setAttribute('fme_dataset', dataset)
        try:
          from openpyxl import load_workbook
          wb = load_workbook(filename=dataset, read_only=True)
          theme_colors = {}
          try:
            theme_colors = get_theme_colors(wb)
            self.debug(unicode(theme_colors))
          except:
            self.error(u'Colud not load theme colors: {}'.format(unicode(traceback.format_exc())))
          for sheet_name in tablelist:
              if '/' in sheet_name:
                  self.warn(u'Skipping Named Range `{}`'.format(sheet_name))
                  continue
              ws = wb[sheet_name]
              feature.setAttribute('_excelcolorreader_status', 'cell' if 'Features' == strategy else 'row')
              for row in ws.rows:
                  if 'Features' == strategy:
                      self.produce_row_features(row, theme_colors, feature, ws.title)
                  else:
                      clone = feature.clone()
                      clone.setAttribute('fme_feature_type', ws.title)
                      if self.set_values(row, theme_colors, clone):
                          self.pyoutput(clone)
          wb.close()
        except Exception as e:
            self.error(unicode(e))
            feature.setAttribute('_excelcolorreader_status', str(e))
            self.pyoutput(feature)
    def produce_row_features(self, row, theme_colors, feature, feature_type):
        from openpyxl.cell.read_only import EmptyCell
        for cell in row:
            if isinstance(cell, EmptyCell): continue
            clone = feature.clone()
            clone.setAttribute('xlsx_row_id', cell.row)
            clone.setAttribute('xlsx_col_id', cell.column)
            clone.setAttribute('fme_feature_type', feature_type)
            if isinstance(cell.value, datetime):
                feature.setAttribute('cellvalue', cell.value.strftime('%Y%m%d%H%M%S'))
            else:
                feature.setAttribute('cellvalue', cell.value)
            if cell.fill is not None:
                color = cell.fill.start_color
                clone.setAttribute('color_type', color.type)
                rgb = evaluate_color(color, theme_colors)
                if rgb is not None:
                    fme_color = ','.join([str(float(x)/255) for x in rgb])
                    clone.setAttribute('fme_fill_color', fme_color)
                    clone.setAttribute('rgb', ','.join(map(str, rgb)))
            self.pyoutput(clone)
    def set_values(self, row, theme_colors, feature):
        from openpyxl.cell.read_only import EmptyCell
        n = 0
        attr_names = []
        rgb_values = []
        fme_colors = []
        color_types = []
        for cell in row:
            if isinstance(cell, EmptyCell): continue
            attr_name = 'col_{}'.format(cell.column)
            if isinstance(cell.value, datetime):
                feature.setAttribute(attr_name, cell.value.strftime('%Y%m%d%H%M%S'))
            else:
                feature.setAttribute(attr_name, cell.value)
            feature.setAttribute('xlsx_row_id', cell.row)
            if cell.fill is not None:
                color = cell.fill.start_color
                rgb = evaluate_color(color, theme_colors)
                if rgb is not None:
                    fme_color = ','.join([str(float(x)/255) for x in rgb])
                    attr_names.append(attr_name)
                    rgb_values.append(','.join(map(str, rgb)))
                    fme_colors.append(fme_color)
                    color_types.append(color.type)
            n += 1
        if n and len(attr_names):
            feature.setAttribute('cell_colors{}.attribute_name', attr_names)
            feature.setAttribute('cell_colors{}.rgb', rgb_values)
            feature.setAttribute('cell_colors{}.color_type', color_types)
            feature.setAttribute('cell_colors{}.fme_fill_color', fme_colors)
        return n
    def close(self):
        del self._session
        del self._logfile
