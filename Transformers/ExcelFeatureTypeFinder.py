import fmeobjects
import locale
import math
EPSILON = 0.1

def tostring(val):
    '''
    When FME reads Excel, values that are numbers can happen to be 
    '''
    if type(val) == float:
        f,i = math.modf(val)
        if f <= EPSILON: return '{:.0f}'.format(val)
    elif type(val) in (int, long):
        return str(val)
    return val

class FeatureProcessor(object):
    ACTION_FIND = 'find feature types'
    ACTION_FIND_AND_MAP = 'find and map'
    def __init__(self):
        self.logfile = fmeobjects.FMELogFile()
        self.session = fmeobjects.FMESession()
        self.current_dataset = None
        self.current_feature_type = None
        self.current_mappings = []
        self.enc = locale.getdefaultlocale()[1]
    def reset(self, dataset, feature_type):
        if dataset == self.current_dataset and feature_type == self.current_feature_type:
            return
        self.current_mappings = [] # (<signature>, <destination feature_type>, ((<source attribute>, <destination attribute>)+))
        self.current_dataset = dataset
        self.current_feature_type = feature_type
    #def get_valid_mappings(self, )
    def input(self,feature):
        unused = True
        dataset = feature.getAttribute('_ExcelFeatureTypeFinder_xlsx_dataset')
        fme_feature_type = feature.getAttribute('fme_feature_type')
        
        self.reset(dataset, fme_feature_type)
        
        action = str(self.parse_attribute(feature, '_ExcelFeatureTypeFinder_action', decode=True)).lower()
        drop_unused = str(self.parse_attribute(feature, '_ExcelFeatureTypeFinder_drop_unused', decode=True)).lower() == 'yes'
        continue_past_signature = str(self.parse_attribute(feature, '_ExcelFeatureTypeFinder_continue_past_signature', decode=True)).lower() == 'yes'
        signatures = feature.getAttribute('_ExcelFeatureTypeFinder_feature_type_signatures')
        fieldsep = str(self.parse_attribute(feature,'_ExcelFeatureTypeFinder_field_sep'))
        row_id = feature.getAttribute('xlsx_row_id')
                
        # the slash ('/') and semicolon (';') that we split on are hardcoded in the .fmx-definition
        for l in signatures.split('/'):
            dst_ftype_name, signature = map(self.session.decodeFromFMEParsableText, l.split(';'))
            fields = signature.split(self.session.decodeFromFMEParsableText(fieldsep))
            signature = ','.join(fields)
            if action == FeatureProcessor.ACTION_FIND_AND_MAP:
                for sign, ftype, mapping in self.current_mappings:
                    if sign != signature or dst_ftype_name != ftype: 
                        continue
                    # map this region
                    clone = feature.clone()
                    n_mapped_attributes = 0
                    for src_attr, dst_attr in mapping:
                        n,m,t = feature.getAttributeNullMissingAndType(src_attr)
                        if m:
                            continue
                        if n:
                            clone.setAttributeNullWithType(dst_attr.encode(self.enc),t)
                        else:
                            clone.setAttribute(dst_attr.encode(self.enc), clone.getAttribute(src_attr))
                        clone.removeAttribute(src_attr)
                        feature.removeAttribute(src_attr) # we consume this attribute here and prevents it from being processed as candidate for new mappings 
                        n_mapped_attributes += 1
                    if n_mapped_attributes or not drop_unused:
                        clone.setAttribute('_ExcelFeatureTypeFinder_status', 'mapped')
                        clone.setAttribute('src_feature_type_name', fme_feature_type)
                        clone.setAttribute('fme_feature_type', dst_ftype_name)
                        unused = False
                        self.pyoutput(clone)
                    else:
                        del clone
            # now let's see if there are any new mappings to be found for this signature
            #def matches(self, values):
            col_fields = [x for x in feature.getAllAttributeNames() if x.startswith('col_')]
            col_fields.sort(key=lambda s: int(s[4:])) # numeric sort on value *after* `col_`
            values = map(feature.getAttribute, col_fields)
            start = -1
            end = -1
            prev = -1
            for i in [values.index(x) for x in values if tostring(x) in fields]:
                if start == -1: 
                    start = i
                    end = i
                    prev = i
                    continue
                if prev + 1 != i:
                    break # we've found value but at wrong position
                prev = i
                end = i + 1
            if end - start == len(fields):
                # we've found all fields and in correct order for this signature
                if continue_past_signature:
                    end = len(col_fields)-start
                    fields = map(tostring, values[start:end])
                fields = [x.strip() for x in fields]    
                mapping = zip(col_fields[start:end], [tostring(x).strip() for x in values[start:end]])
                self.current_mappings.append((signature, dst_ftype_name, mapping))
                for attr in col_fields[start:end]:
                    feature.removeAttribute(attr)
                clone = feature.clone()
                clone.setAttribute('_ExcelFeatureTypeFinder_status', 'found')
                clone.setAttribute('src_feature_type_name', fme_feature_type)
                clone.setAttribute('fme_feature_type', dst_ftype_name)
                clone.setAttribute('attribute_rename{}.from', col_fields[start:end])
                clone.setAttribute('attribute_rename{}.to', fields)
                clone.setAttribute('fme_feature_type_name', dst_ftype_name)
                clone.setAttribute('attribute{}.name', fields)
                clone.setAttribute('attribute{}.fme_data_type', ['fme_varchar(50)' for x in fields])
                clone.setAttribute('fme_geometry{}', ['fme_no_geom', 'fme_point'])
                #found_regions.append(clone)
                unused = True
                self.pyoutput(clone)
        if unused and not drop_unused:
            feature.setAttribute('_ExcelFeatureTypeFinder_status', 'unused')
            self.pyoutput(feature)
        else:
            del feature

    def parse_attribute(self, feature, attributeName, decode=False, default=None):
        n,m,t = feature.getAttributeNullMissingAndType(attributeName)
        if n or m: return default
        val = feature.getAttribute(attributeName)
        if t in [fmeobjects.FME_ATTR_BOOLEAN,fmeobjects.FME_ATTR_INT8,fmeobjects.FME_ATTR_UINT8,fmeobjects.FME_ATTR_INT16, fmeobjects.FME_ATTR_UINT16, fmeobjects.FME_ATTR_INT32, fmeobjects.FME_ATTR_UINT32, fmeobjects.FME_ATTR_REAL32, fmeobjects.FME_ATTR_REAL64, fmeobjects.FME_ATTR_REAL80, fmeobjects.FME_ATTR_INT64, fmeobjects.FME_ATTR_UINT64]:
            return val
        if decode:
            return self.session.decodeFromFMEParsableText(val)
        return val
    def info(self, msg):
        self.logfile.logMessageString('ExcelFeatureTypeFinder: {}'.format(msg), fmeobjects.FME_WARN)
    def close(self):
        del self.logfile
        del self.session
