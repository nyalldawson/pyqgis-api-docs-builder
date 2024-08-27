#!/usr/bin/env python3

import argparse
import inspect
import re
from collections import defaultdict
from os import makedirs
from shutil import rmtree
from string import Template

import yaml

with open("pyqgis_conf.yml") as f:
    cfg = yaml.safe_load(f)


parser = argparse.ArgumentParser(description="Create RST files for QGIS Python API Documentation")
parser.add_argument("--version", "-v", dest="qgis_version", default="master")
parser.add_argument(
    "--package",
    "-p",
    dest="package_limit",
    default=None,
    nargs="+",
    choices=["core", "gui", "server", "analysis", "processing", "_3d"],
    help="limit the build of the docs to one package (core, gui, server, analysis, processing, 3d) ",
)
parser.add_argument(
    "--class",
    "-c",
    dest="single_class",
    default=None,
    nargs="+",
    help="limit the build of the docs to a single class",
)
args = parser.parse_args()

if args.package_limit:
    packages = args.package_limit
    exec("from qgis import {}".format(", ".join(packages)))
    packages = {pkg: eval(pkg) for pkg in packages}
else:
    from qgis import _3d, analysis, core, gui, processing, server

    packages = {
        "core": core,
        "gui": gui,
        "analysis": analysis,
        "server": server,
        "processing": processing,
        "_3d": _3d,
    }


def ltr_tag(v):
    try:
        pr = int(v.split(".")[1])  # 3.22 => 22
        if (pr + 2) % 3 == 0:  # LTR is every 3 releases starting at 3.4
            return " (LTR)"
    except IndexError:
        pass
    return ""


current_stable = cfg["current_stable"]
current_ltr = cfg["current_ltr"]
current_stable_minor = int(current_stable.split(".")[1])
current_ltr_minor = int(current_ltr.split(".")[1])
old_versions_links = ", ".join(
    reversed(
        [
            f"`3.{v} <https://github.com/qgis/pyqgis-api-docs-builder/releases/download/3.{v}/pyqgis-docs-3.{v}.zip>`_"
            for v in range(0, current_stable_minor, 2)
            if v != current_ltr_minor
        ]
    )
)

py_ext_sig_re = re.compile(
    r"""^(?:([\w.]+::)?([\w.]+\.)?(\w+)\s*(?:\((.*)\)(?:\s*->\s*([\w.]+(?:\[.*?\])?))?(?:\s*\[(signal)\])?)?)?$"""
)


class RecursiveTemplate(Template):
    """
    Template subclass which performs recursive substitution on a string.
    """

    def __init__(self, template):
        super().__init__(template)
        self.depth = 0
        self.max_depth = 10  # Prevent infinite recursion

    def substitute(self, **kws):
        self.depth = 0
        return self._recursive_substitute(**kws)

    def _recursive_substitute(self, **kws):
        if self.depth > self.max_depth:
            raise ValueError("Max recursion depth exceeded")

        self.depth += 1
        try:
            result = super().safe_substitute(**kws)
        except RecursionError:
            return self.template

        if "$" in result:
            return self.__class__(result)._recursive_substitute(**kws)

        return result


# Make sure :numbered: is only specified in the top level index - see
# sphinx docs about this.
document_header = f"""
:tocdepth: 5

Welcome to the QGIS Python API documentation project
==============================================================

Introduction
------------

`QGIS <https://qgis.org>`_ is a user friendly Open Source Geographic Information System (GIS) that runs on Linux, Unix, macOS, and Windows.
QGIS supports vector, raster, and database formats. QGIS is licensed under the GNU General Public License.
QGIS lets you browse and create map data on your computer. It supports many common spatial data formats (e.g. ESRI ShapeFile, GeoPackage, PostGIS, geotiff).
QGIS supports plugins to do things like display tracks from your GPS. QGIS is Open Source software and it is free of cost (`download here <https://www.qgis.org/en/site/forusers/download.html>`_).
We welcome contributions from our user community in the form of code contributions, bug fixes, bug reports, contributed documentation,
advocacy and supporting other users on our mailing lists and forums. Financial contributions are also welcome.

QGIS source code is available at https://github.com/qgis/QGIS.
There is also a `C++ version of the API documentation <https://api.qgis.org/api>`_ available.

Versions of the API
---------------------------

* Documentation for master: https://qgis.org/pyqgis/master
* Documentation for current stable {current_stable}: https://qgis.org/pyqgis/{current_stable}
* Documentation for current LTR {current_ltr}: https://qgis.org/pyqgis/{current_ltr}

See `Backwards Incompatible Changes <https://api.qgis.org/api/master/api_break.html>`_ for information about incompatible changes to API between releases.

Earlier versions of the documentation are also available as downloads: {old_versions_links}.

Communication channels
----------------------

For support we encourage you to join our `mailing lists <https://qgis.org/en/site/forusers/support.html#mailing-lists>`_ for users and developers.
Some QGIS users and developers can also often be found in channels such as Matrix, Telegram,...

Bug Reporting
--------------

If you think you have found a bug in the documentation, please report it using our `bug tracker <https://github.com/qgis/pyqgis/issues>`_.
When reporting bugs, please be available to follow up on your initial report.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

"""

document_footer = """
Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`"""

package_header = """

PACKAGENAME
===================================

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: PACKAGENAME:

"""

inheritance_diagram = """
.. inheritance-diagram:: qgis.$PACKAGE.$CLASS
   :parts: 1
"""

class_toc = """
.. autoautosummary:: qgis.$PACKAGE.$CLASS
    :enums:
    :nosignatures:
    :exclude-members: $EXCLUDE_METHODS

.. autoautosummary:: qgis.$PACKAGE.$CLASS
    :methods:
    :nosignatures:
    :exclude-members: $EXCLUDE_METHODS

.. autoautosummary:: qgis.$PACKAGE.$CLASS
    :static_methods:
    :nosignatures:
    :exclude-members: $EXCLUDE_METHODS

.. autoautosummary:: qgis.$PACKAGE.$CLASS
    :signals:
    :nosignatures:
    :exclude-members: $EXCLUDE_METHODS

.. autoautosummary:: qgis.$PACKAGE.$CLASS
    :attributes:
    :exclude-members: $EXCLUDE_METHODS
"""

MODULE_TOC_MAX_COLUMN_SIZES = [300, 500]


def write_header(header: str, level=1) -> str:
    """
    Writes a markdown header
    """
    res = header + "\n"
    if level == 1:
        res += "-" * len(header)
    elif level == 2:
        res += "=" * len(header)
    else:
        assert False

    return res + "\n"


def extract_summary(doc: str | None) -> str:
    """
    Extract summary from docstring.
    """
    if not doc:
        return ""

    doc = [line for line in doc.split("\n") if not line or not py_ext_sig_re.match(line)]

    # Skip a blank lines at the top
    while doc and not doc[0].strip():
        doc.pop(0)

    # If there's a blank line, then we can assume the first sentence /
    # paragraph has ended, so anything after shouldn't be part of the
    # summary
    for i, piece in enumerate(doc):
        if not piece.strip():
            doc = doc[:i]
            break

    if not doc:
        return ""

    return " ".join(doc)


def make_table_row(contents: list[str]):
    """
    Adds a row to the module TOC table
    """
    res = "|"
    for column, cell in enumerate(contents):
        formatted_cell = cell[: MODULE_TOC_MAX_COLUMN_SIZES[column]]
        formatted_cell = formatted_cell + " " * (
            MODULE_TOC_MAX_COLUMN_SIZES[column] - len(formatted_cell)
        )
        res += formatted_cell + "|"
    res += "\n"
    for column, _ in enumerate(contents):
        res += f"+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[column]}"
    res += "+\n"
    return res


def generate_docs():
    """Generate RST documentation by introspection of QGIS libs.

    The function will create a docs directory (removing it first if it
    already exists) and then populate it with an autogenerated sphinx
    document hierarchy with one RST document per QGIS class.

    The generated RST documents will be then parsed by sphinx's autodoc
    plugin to extract python API documentation from them.

    After this function has completed, you should run the 'make html'
    sphinx command to generate the actual html output.
    """

    # qgis_version = 'master'
    qgis_version = args.qgis_version

    rmtree(f"build/{qgis_version}", ignore_errors=True)
    rmtree(f"api/{qgis_version}", ignore_errors=True)
    makedirs("api", exist_ok=True)
    makedirs(f"api/{qgis_version}")
    index = open(f"api/{qgis_version}/index.rst", "w")
    # Read in the standard rst template we will use for classes
    index.write(document_header)

    with open("rst/qgis_pydoc_template.txt") as template_file:
        template_text = template_file.read()
    template = RecursiveTemplate(template_text)

    # Iterate over every class in every package and write out an rst
    # template based on standard rst template

    for package_name, package in packages.items():
        makedirs(f"api/{qgis_version}/{package_name}")
        index.write(f"   {package_name}/index\n")

        package_index = open(f"api/{qgis_version}/{package_name}/index.rst", "w")
        # Read in the standard rst template we will use for classes
        package_index.write(package_header.replace("PACKAGENAME", package_name))
        package_custom_toc = defaultdict(str)

        for class_name, _class in extract_package_classes(package):
            exclude_methods = set()
            header = ""
            toc = ""

            bases_and_subclass_header = ""
            if hasattr(_class, "__bases__") and _class.__bases__:

                def export_bases(_b):

                    res = ""
                    for _base in _b.__bases__:
                        if _base.__name__ in ("wrapper", "simplewrapper", "object"):
                            continue
                        res += make_table_row(
                            [
                                f"`{_base.__name__} <{_base.__name__}.html>`_",
                                extract_summary(_base.__doc__),
                            ]
                        )
                        if hasattr(_base, "__bases__"):
                            res += export_bases(_base)
                    return res

                base_header = export_bases(_class)
                if base_header:
                    bases_and_subclass_header += "\n" + write_header("Base classes", 2)
                    bases_and_subclass_header += f"\n+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[0]}+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[1]}+\n"
                    bases_and_subclass_header += base_header

            if hasattr(_class, "__subclasses__") and _class.__subclasses__():
                bases_and_subclass_header += "\n" + write_header("Subclasses", 2)
                bases_and_subclass_header += f"\n+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[0]}+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[1]}+\n"

                for subclass in _class.__subclasses__():
                    bases_and_subclass_header += make_table_row(
                        [
                            f"`{subclass.__name__} <{subclass.__name__}.html>`_",
                            extract_summary(subclass.__doc__),
                        ]
                    )

            if inspect.isclass(_class):
                class_doc = _class.__doc__
                # only keep the actual class doc string part. SIP will
                # append the constructor signatures and docs at the end
                # of the class doc, so let's trim those off.
                # They'll get included later in the actual listing of
                # class methods
                if class_doc:
                    lines = class_doc.split("\n")
                    init_idx = 0
                    for init_idx, line in enumerate(lines):
                        if re.match(rf"^{_class.__name__}\(", line):
                            break

                    header = "\n".join(lines[:init_idx])

                if bases_and_subclass_header:
                    if header:
                        header += "\n"
                    header += write_header("Class Hierarchy")
                    header += inheritance_diagram
                    header += bases_and_subclass_header
                toc = class_toc

            for method in dir(_class):
                if not hasattr(_class, method):
                    continue

                class_doc = getattr(_class, method).__doc__

                if class_doc and all(
                    py_ext_sig_re.match(line) for line in str(class_doc).split("\n")
                ):
                    # print(f'docs are function signature only {class_doc}')
                    class_doc = None

                if hasattr(_class, "__bases__"):
                    for base in _class.__bases__:
                        if hasattr(base, method) and (
                            not class_doc or getattr(base, method).__doc__ == str(class_doc)
                        ):
                            # print(f'skipping overridden method with no new doc {method}')
                            exclude_methods.add(method)
                            break
                        elif hasattr(base, method):
                            # print(f'overrides {method} with different docs')
                            # print(class_doc)
                            # print(getattr(base, method).__doc__)
                            pass

            substitutions = {
                "PACKAGE": package_name,
                "CLASS": class_name,
                "EXCLUDE_METHODS": ",".join(exclude_methods),
                "HEADER_CONTENT": header,
                "TABLE_OF_CONTENTS": toc,
            }
            class_template = template.substitute(**substitutions)
            class_rst = open(f"api/{qgis_version}/{package_name}/{class_name}.rst", "w")
            print(class_template, file=class_rst)
            class_rst.close()
            package_index.write(f"   {class_name}\n")
            class_doc = _class.__doc__
            summary = ""
            if class_doc:
                summary = extract_summary(class_doc)
            row_contents = [f"`{class_name} <{class_name}.html>`_", summary or ""]
            group = ".".join(_class.__group__) if hasattr(_class, "__group__") else ""
            package_custom_toc[group] += make_table_row(row_contents)

        sorted_package_groups = sorted(
            package_custom_toc.keys(), key=lambda x: cfg["group-names"].get(x, x)
        )
        if len(sorted_package_groups) > 1:
            # Add TOC for groups
            package_index.write("\n")
            for package_group in sorted_package_groups:
                if not package_group:
                    continue

                anchor = f'{package_name.replace("_", "")}.{package_group}'.replace(".", "_")
                group_name = cfg["group-names"].get(package_group, package_group)
                package_index.write(f"- :ref:`{group_name}<{anchor}>`\n")

            package_index.write("\n")

        for package_group in sorted_package_groups:
            group_custom_toc = package_custom_toc[package_group]
            if package_group:
                anchor = f'{package_name.replace("_", "")}.{package_group}'.replace(".", "_")
                package_index.write(f".. _{anchor}:\n\n")
                group_name = cfg["group-names"].get(package_group, package_group)
                package_index.write(f"{group_name}\n{'-' * len(group_name)}\n")
            package_index.write(
                f"\n+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[0]}+{'-' * MODULE_TOC_MAX_COLUMN_SIZES[1]}+\n"
            )
            package_index.write(group_custom_toc)
            package_index.write("\n")

        package_index.close()

    index.write(document_footer)
    index.close()


def extract_package_classes(package):
    """Extract the classes from the package provided.

    :param package: The  package to extract groups from e.g. qgis.core.
    :type package: object

    :returns: A list of classes alphabetically ordered.
    :rtype: list
    """
    classes = []

    for class_name in dir(package):
        if class_name.startswith("_"):
            continue
        if args.single_class:
            found = False
            for _class in args.single_class:
                if class_name.startswith(_class):
                    found = True
                    break
            if not found:
                continue
        if class_name in cfg["skipped"]:
            continue

        _class = getattr(package, class_name)
        if hasattr(_class, "__name__") and class_name != _class.__name__:
            # print(f"Skipping alias {class_name}, {_class.__name__}")
            continue

        # if not re.match('^Qgi?s', class_name):
        #     continue
        classes.append((class_name, _class))

    return sorted(classes, key=lambda x: x[0])


if __name__ == "__main__":
    generate_docs()
