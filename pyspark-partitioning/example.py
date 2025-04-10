import xml.etree.ElementTree as ET
import requests
import json
from urllib.parse import urljoin

DEFAULT_NUGET_URL = "https://api.nuget.org/v3/index.json"

def parse_packages_config(path="packages.config"):
    tree = ET.parse(path)
    root = tree.getroot()
    return [(pkg.attrib["id"], pkg.attrib["version"]) for pkg in root.findall("package")]

def parse_nuget_config(path="NuGet.config"):
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {'': 'http://schemas.microsoft.com/packaging/2010/07/packaging'}
        sources = {}
        for add in root.findall(".//packageSources/add"):
            key = add.attrib.get("key")
            value = add.attrib.get("value")
            if value:
                sources[key] = value.rstrip("/")
        return list(sources.values())
    except Exception as e:
        print(f"Could not parse NuGet.config: {e}")
        return [DEFAULT_NUGET_URL]

def get_registration_base(source_url):
    """Fetch the registration base URL from a NuGet v3 feed."""
    index_url = urljoin(source_url + "/", "v3/index.json")
    try:
        response = requests.get(index_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        for res in data.get("resources", []):
            if res["@type"].startswith("RegistrationsBaseUrl"):
                return res["@id"].rstrip("/")
    except Exception as e:
        print(f"Warning: Could not get registration base from {index_url} - {e}")
    return None

def get_dependencies(package_id, version, sources):
    for source in sources:
        base_url = get_registration_base(source)
        if not base_url:
            continue
        url = f"{base_url}/{package_id.lower()}/{version}.json"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                deps = []
                for entry in data.get("dependencyGroups", []):
                    for dep in entry.get("dependencies", []):
                        deps.append((dep["id"], dep.get("range", "unknown")))
                return deps
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
    print(f"Failed to fetch dependencies for {package_id} {version}")
    return []

def resolve_all_dependencies(packages, sources):
    top_level = dict(packages)
    all_deps = {}
    visited = set()

    def visit(pkg_id, version):
        key = f"{pkg_id.lower()}:{version}"
        if key in visited:
            return
        visited.add(key)

        deps = get_dependencies(pkg_id, version, sources)
        all_deps[pkg_id] = {"version": version, "dependencies": deps}
        for dep_id, dep_version in deps:
            stripped_version = dep_version.strip("[]() ")
            if dep_id not in all_deps:
                visit(dep_id, stripped_version or "latest")

    for pkg_id, version in packages:
        visit(pkg_id, version)

    return all_deps, top_level

def generate_json(all_deps, top_level):
    output = {
        "topLevel": [],
        "transitive": []
    }
    for pkg_id in top_level:
        version = all_deps[pkg_id]["version"]
        output["topLevel"].append({
            "id": pkg_id,
            "requested": version,
            "resolved": version
        })

    for pkg_id, info in all_deps.items():
        if pkg_id not in top_level:
            output["transitive"].append({
                "id": pkg_id,
                "resolved": info["version"]
            })

    return output

if __name__ == "__main__":
    packages = parse_packages_config("packages.config")
    sources = parse_nuget_config("NuGet.config")
    all_deps, top_level = resolve_all_dependencies(packages, sources)
    result = generate_json(all_deps, top_level)
    print(json.dumps(result, indent=2))
