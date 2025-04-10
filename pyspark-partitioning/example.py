import xml.etree.ElementTree as ET
import requests

NUGET_BASE_URL = "https://api.nuget.org/v3/registration5-gz-semver1"

def get_dependencies(package_id, version):
    """Fetch dependencies from NuGet package metadata."""
    url = f"{NUGET_BASE_URL}/{package_id.lower()}/{version}.json"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"Failed to fetch {package_id} {version}")
        return []

    data = response.json()
    deps = []
    for entry in data.get("dependencyGroups", []):
        for dep in entry.get("dependencies", []):
            deps.append((dep["id"], dep.get("range", "unknown")))
    return deps

def parse_packages_config(file_path):
    """Parse packages.config and return a list of (id, version)."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    return [(pkg.attrib["id"], pkg.attrib["version"]) for pkg in root.findall("package")]

def resolve_all_dependencies(packages):
    """Recursively resolve all transitive dependencies."""
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
            if dep_id not in all_deps:
                visit(dep_id, dep_version.strip('[]()'))  # naive version cleanup

    for pkg_id, version in packages:
        visit(pkg_id, version)

    return all_deps, top_level

def print_package_list(all_deps, top_level):
    print("Project 'MyProject' has the following package references")
    print("   [net48]:")
    print("   Top-level Package               Requested   Resolved")
    for pkg_id in top_level:
        version = all_deps[pkg_id]["version"]
        print(f"   > {pkg_id:<30} {version:<10} {version}")

    print("\n   Transitive Package")
    for pkg_id, info in all_deps.items():
        if pkg_id not in top_level:
            print(f"   > {pkg_id:<30} -           {info['version']}")

if __name__ == "__main__":
    packages = parse_packages_config("packages.config")
    all_deps, top_level = resolve_all_dependencies(packages)
    print_package_list(all_deps, top_level)
