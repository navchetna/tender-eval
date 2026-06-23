from comps.core.logger import CustomLogger

__all__ = [
  "CustomLogger",
  "DocPath",
  "EmbedDoc",
  "EmbedMultimodalDoc",
  "SearchedDoc",
  "SearchedMultimodalDoc",
  "TextDoc",
  "opea_microservices",
  "register_microservice",
  "MicroService",
  "MegaServiceEndpoint",
  "ServiceRoleType",
  "ServiceType",
  "statistics_dict",
  "register_statistics",
  "ServiceOrchestrator",
]

_LAZY_EXPORTS = {
  "DocPath": ("comps.proto.docarray", "DocPath"),
  "EmbedDoc": ("comps.proto.docarray", "EmbedDoc"),
  "EmbedMultimodalDoc": ("comps.proto.docarray", "EmbedMultimodalDoc"),
  "SearchedDoc": ("comps.proto.docarray", "SearchedDoc"),
  "SearchedMultimodalDoc": ("comps.proto.docarray", "SearchedMultimodalDoc"),
  "TextDoc": ("comps.proto.docarray", "TextDoc"),
  "opea_microservices": ("comps.core.microservice", "opea_microservices"),
  "register_microservice": ("comps.core.microservice", "register_microservice"),
  "MicroService": ("comps.core.microservice", "MicroService"),
  "MegaServiceEndpoint": ("comps.core.constants", "MegaServiceEndpoint"),
  "ServiceRoleType": ("comps.core.constants", "ServiceRoleType"),
  "ServiceType": ("comps.core.constants", "ServiceType"),
  "statistics_dict": ("comps.core.base_statistics", "statistics_dict"),
  "register_statistics": ("comps.core.base_statistics", "register_statistics"),
  "ServiceOrchestrator": ("comps.core.orchestrator", "ServiceOrchestrator"),
}


def __getattr__(name):
  if name not in _LAZY_EXPORTS:
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

  from importlib import import_module

  module_name, attr_name = _LAZY_EXPORTS[name]
  attr = getattr(import_module(module_name), attr_name)
  globals()[name] = attr
  return attr