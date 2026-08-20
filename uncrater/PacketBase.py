import os, sys
import hexdump
from .coreloop import pycoreloop,pycoreloop_203,pycoreloop_305,pycoreloop_307
from .schema_registry import SchemaBinding, SchemaConflictError, resolve_wire_version
pystruct = pycoreloop.pystruct
pystruct_203 = pycoreloop_203.pystruct
pystruct_305 = pycoreloop_305.pystruct
pystruct_307 = pycoreloop_307.pystruct


class PacketBase:
    def __init__ (self, appid, blob = None, blob_fn = None, version=None,
                  schema=None, reported_version=None, schema_variant=None,
                  schema_assumed=None, evidence=None, diagnostic_override=False,
                  original_appid=None, **kwargs):
        if (blob is None) and (blob_fn is None):
            raise ValueError
        self.appid = appid
        self.original_appid = appid if original_appid is None else original_appid
        self._blob = blob
        self._blob_fn = blob_fn

        if (reported_version is not None and version is not None
                and reported_version != version):
            raise SchemaConflictError("version and reported_version disagree")
        if reported_version is None:
            reported_version = version
        if schema is None:
            resolution = resolve_wire_version(
                reported_version,
                variant=schema_variant,
                evidence=evidence,
                diagnostic_override=diagnostic_override,
            )
            schema = resolution.binding
            resolved_schema_assumed = resolution.schema_assumed
        else:
            if not isinstance(schema, SchemaBinding):
                raise TypeError("schema must be a SchemaBinding")
            resolved_schema_assumed = (
                reported_version is None
                or reported_version not in schema.accepted_reported_versions
            )
            if evidence is not None or schema_variant is not None:
                resolution = resolve_wire_version(
                    reported_version,
                    variant=schema_variant,
                    evidence=evidence,
                    diagnostic_override=diagnostic_override,
                )
                if resolution.binding is not schema:
                    raise SchemaConflictError(
                        f"Packet evidence selects {resolution.binding.binding_key}, "
                        f"not {schema.binding_key}"
                    )
                resolved_schema_assumed = resolution.schema_assumed
            if (reported_version is not None
                    and reported_version not in schema.accepted_reported_versions
                    and evidence is None and schema_variant is None):
                resolution = resolve_wire_version(
                    reported_version,
                    diagnostic_override=diagnostic_override,
                )
                if resolution.binding is not schema:
                    raise SchemaConflictError(
                        f"Reported version 0x{reported_version:X} does not match "
                        f"binding {schema.binding_key}"
                    )
                resolved_schema_assumed = resolution.schema_assumed

        if schema_assumed is not None:
            if not isinstance(schema_assumed, bool):
                raise TypeError("schema_assumed must be a bool or None")
            if schema_assumed != resolved_schema_assumed:
                raise SchemaConflictError("schema_assumed contradicts schema resolution")
        schema_assumed = resolved_schema_assumed

        # Keep the on-wire report separate from the frozen decoder selected for it
        self.schema = schema
        self.schema_id = schema.canonical_schema_id
        self.reported_version = reported_version
        self.schema_assumed = bool(schema_assumed)
        self.binding_provenance = schema.binding_provenance
        self._version = reported_version
        self._is_read = False
        for key, value in kwargs.items():
            setattr(self, key, value)
        if blob is not None:
            self._read()
        

        
    def _read(self):
        if self._is_read:
            return
        if self._blob is None:
            self._blob = open(self._blob_fn,"rb").read()    

    def read(self):
        self._read()

    def _analyze_attr(self, attr_name: str, obj: object, full_attr_name: str) -> None:
        attr = getattr(obj, attr_name)
        full_attr_name += f'{attr_name}.'
        if isinstance(attr, object) and type(attr).__module__ != 'builtins':
            self._analyze_hk(attr, full_attr_name)
        else:
            self.attr_dict[full_attr_name.strip('.')].append(attr)

    def _analyze_hk(self, obj: object, full_attr_name='') -> None:
        # slotted classes generated in core_loop.py
        print (obj,full_attr_name)
        if hasattr(obj, '__slots__'):
            for slot in obj.__slots__:
                if slot[0] == '_':
                    continue
                self._analyze_attr(slot, obj, full_attr_name)
        # top level Packet class
        elif obj.__class__.__module__ != 'builtins':
            for attr_name in vars(obj):
                if attr_name[0] == '_':
                    continue
                self._analyze_attr(attr_name, obj, full_attr_name)


    def keys(self):
        def it_keys(d):
            l = []
            klist = getattr(d,"__slots__") if hasattr(d,"__slots__") else dir(d)
            for k in klist:
                if k[0]=='_':
                    continue        
                a = getattr(d,k)
                if not hasattr(a, "__slots__"):
                    if not (callable(a)):
                        l.append(k)
                else:
                    for sk in it_keys(a):
                        l.append(k+'.'+sk)
            return l 
        return it_keys(self)
    
    def __getitem__(self,name):
        def get_dotted(obj,name):
            if '.' in name:
                i = name.find('.')
                first,second = name[:i], name[i+1:]
                if hasattr(obj,first):
                    return get_dotted(getattr(obj,first),second)
                else:
                    return None
            else:
                return getattr(obj,name)
        return get_dotted(self,name)

    def xxd(self):
        """ xxd style dump of the contents"""
        self._read()
        return hexdump.hexdump(self.blob,result='return')

    @property
    def desc(self):
        return  "generic"


    def info(self):
        """ ASCII readable description.
        To be specialized
        """
        return self.xxd()

    def copy_attrs (self,src):
        for attr in dir(src): 
            if attr[0] == '_':
                continue
            setattr(self, attr, getattr(src, attr))
