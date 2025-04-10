import xml.etree.ElementTree as ET
import requests
import json

NUGET_BASE_URL = "https://api.nuget.org/v3/registration5-gz-semver1"

def get_dependencies(package_id, version):
    url = f"{NUGET_BASE_URL}/{package_id.lower()}/{version}.json"
    response = requests.get(url)
    if response.status_code != 200:
        return []
    data = response.json()
    deps = []
    for entry in data.get("dependencyGroups", []):
        for dep in entry.get("dependencies", []):
            deps.append((dep["id"], dep.get("range", "unknown")))
    return deps

def parse_packages_config(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    return [(pkg.attrib["id"], pkg.attrib["version"]) for pkg in root.findall("package")]

def resolve_all_dependencies(packages):
    top_level = dict(packages)
    all_deps = {}
    visited = set()

    def visit(pkg_id, version):
        key = f"{pkg_id.lower()}:{version}"
        if key in visited:
            return
        visited.add(key)

        deps = get_dependencies(pkg_id, version)
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
    all_deps, top_level = resolve_all_dependencies(packages)
    result = generate_json(all_deps, top_level)
    print(json.dumps(result, indent=2))
