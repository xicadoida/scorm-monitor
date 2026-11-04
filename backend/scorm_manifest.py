"""Estrutura mínima SCORM 1.2/2004; sem rede, DTD ou entidades XML."""
from dataclasses import dataclass
from pathlib import Path
import posixpath
from urllib.parse import quote, unquote, urlsplit

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException


class InvalidManifest(ValueError):
    pass


@dataclass(frozen=True)
class ManifestInfo:
    version: str
    launcher: str


def local_reference(root, base, reference, allow_external=False):
    url = urlsplit(reference)
    if allow_external and url.scheme in {'http', 'https'} and url.netloc:
        return None
    if url.scheme or url.netloc or not url.path:
        raise InvalidManifest('Referência SCORM deve apontar para arquivo local.')
    path = unquote(url.path)
    if '\\' in path or ':' in path or path.startswith('/') or any(ord(c) < 32 for c in path):
        raise InvalidManifest('Referência SCORM contém caminho inseguro.')
    relative = posixpath.normpath(posixpath.join(base, path))
    if relative == '..' or relative.startswith('../'):
        raise InvalidManifest('Referência SCORM sai da raiz do pacote.')
    target = root.joinpath(*relative.split('/'))
    if not target.resolve().is_relative_to(root.resolve()) or not target.is_file():
        raise InvalidManifest('Arquivo referenciado pelo manifesto não encontrado.')
    return quote(relative, safe='/') + (f'?{url.query}' if url.query else '') + (f'#{url.fragment}' if url.fragment else '')


def validate_manifest(root, maximum=2 * 1024 * 1024):
    root = Path(root)
    path = root / 'imsmanifest.xml'
    if path.stat().st_size > maximum:
        raise InvalidManifest('Manifesto excede o limite de tamanho.')
    data = path.read_bytes()
    if not data.strip():
        raise InvalidManifest('imsmanifest.xml está vazio.')
    try:
        manifest = ElementTree.fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise InvalidManifest('Manifesto XML inválido ou contém DTD/entidades não permitidas.') from error
    namespace, _, name = manifest.tag[1:].partition('}') if manifest.tag.startswith('{') else ('', '', manifest.tag)
    versions = {
        'http://www.imsproject.org/xsd/imscp_rootv1p1p2': ('1.2', 'http://www.adlnet.org/xsd/adlcp_rootv1p2'),
        'http://www.imsglobal.org/xsd/imscp_v1p1': ('2004', 'http://www.adlnet.org/xsd/adlcp_v1p3'),
    }
    if name != 'manifest' or namespace not in versions or not manifest.get('identifier', '').strip():
        raise InvalidManifest('Manifesto deve identificar um pacote SCORM 1.2 ou 2004.')
    version, adl = versions[namespace]
    tag = lambda name: f'{{{namespace}}}{name}'
    bases = {}

    def map_bases(node, inherited=''):
        value = node.get('{http://www.w3.org/XML/1998/namespace}base', '')
        if value:
            parsed = urlsplit(value)
            decoded = unquote(parsed.path)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or decoded.startswith('/') or '\\' in decoded or ':' in decoded:
                raise InvalidManifest('xml:base inseguro no manifesto.')
            inherited = posixpath.normpath(posixpath.join(inherited, decoded))
            if inherited == '..' or inherited.startswith('../'):
                raise InvalidManifest('xml:base sai da raiz do pacote.')
        bases[id(node)] = inherited
        for child in node:
            map_bases(child, inherited)

    map_bases(manifest)
    resources_node = manifest.find(tag('resources'))
    organizations = manifest.find(tag('organizations'))
    if resources_node is None or organizations is None:
        raise InvalidManifest('Manifesto deve conter organizations e resources.')
    resources = {}
    for resource in resources_node.findall(tag('resource')):
        identifier = resource.get('identifier', '')
        if not identifier or identifier in resources:
            raise InvalidManifest('Identificadores de recursos ausentes ou duplicados.')
        resources[identifier] = resource
    for resource in resources.values():
        for file in resource.findall(tag('file')):
            local_reference(root, bases[id(file)], file.get('href', ''), allow_external=True)
        for dependency in resource.findall(tag('dependency')):
            if dependency.get('identifierref') not in resources:
                raise InvalidManifest('Dependência de recurso não encontrada.')
    orgs = organizations.findall(tag('organization'))
    default = organizations.get('default')
    selected = next((org for org in orgs if org.get('identifier') == default), None) if default else next(iter(orgs), None)
    if selected is None:
        raise InvalidManifest('Organização padrão não encontrada.')
    launchers = {}
    for organization in orgs:
        for item in organization.iter(tag('item')):
            reference = item.get('identifierref')
            if reference is None:
                continue
            resource = resources.get(reference)
            if resource is None:
                raise InvalidManifest('Item referencia recurso inexistente.')
            scorm_type = resource.get(f'{{{adl}}}scormtype') or resource.get(f'{{{adl}}}scormType')
            if scorm_type not in {'sco', 'asset'} or resource.get('type') != 'webcontent':
                raise InvalidManifest('Recurso de aprendizagem SCORM inválido.')
            launcher = local_reference(root, bases[id(resource)], resource.get('href', ''))
            if scorm_type == 'sco':
                launchers[id(item)] = launcher
    launcher = next((launchers[id(item)] for item in selected.iter(tag('item')) if id(item) in launchers), None)
    if launcher is None:
        raise InvalidManifest('Organização padrão não contém SCO local executável.')
    return ManifestInfo(version, launcher)
