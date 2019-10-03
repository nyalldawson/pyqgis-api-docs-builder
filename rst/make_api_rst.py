#!/usr/bin/env python3
# coding=utf-8

from collections import OrderedDict
from string import Template
from os import makedirs

import re
from shutil import rmtree

import argparse

parser = argparse.ArgumentParser(description='Create RST files for QGIS Python API Documentation')
parser.add_argument('--version', '-v', dest='qgis_version', default="master")
parser.add_argument('--package', '-p', dest='package_limit', default=None, nargs='+',
# action='store_const', default=None, type=str,
                   choices=['core', 'gui', 'server', 'analysis', 'processing'],
                   help='limit the build of the docs to one package (core, gui, server, analysis, processing) ')
parser.add_argument('--class', '-c', dest='class_limit',
                   help='limit the build of the docs to a single class')
args = parser.parse_args()

if (args.package_limit):
    exec("from qgis import {}".format(', '.join(args.package_limit)))
    packages = {pkg: eval(pkg) for pkg in args.package_limit}
else:
    if (args.qgis_version == 3.4):
        from qgis import core, gui, analysis, server
        packages = {'core': core, 'gui': gui, 'analysis': analysis, 'server': server}
    else:
        from qgis import core, gui, analysis, server, processing
        packages = {'core': core, 'gui': gui, 'analysis': analysis, 'server': server, 'processing': processing}
 

# Make sure :numbered: is only specified in the top level index - see
# sphinx docs about this.
document_header = """
:tocdepth: 5

Welcome to the QGIS Python API documentation project
==============================================================

.. toctree::
   :maxdepth: 5
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
   :maxdepth: 4
   :caption: PACKAGENAME:

"""


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

    #qgis_version = 'master'
    qgis_version = args.qgis_version

    rmtree('build/{}'.format(qgis_version), ignore_errors=True)
    rmtree('api/{}'.format(qgis_version), ignore_errors=True)
    makedirs('api', exist_ok=True)
    makedirs('api/{}'.format(qgis_version))
    index = open('api/{}/index.rst'.format(qgis_version), 'w')
    # Read in the standard rst template we will use for classes
    index.write(document_header)

    with open('rst/qgis_pydoc_template.txt', 'r') as template_file:
        template_text = template_file.read()
    template = Template(template_text)

    # Iterate over every class in every package and write out an rst
    # template based on standard rst template

    for package_name, package in packages.items():
        makedirs('api/{}/{}'.format(qgis_version, package_name))
        index.write('   {}/index\n'.format(package_name))

        package_index = open('api/{}/{}/index.rst'.format(qgis_version, package_name), 'w')
        # Read in the standard rst template we will use for classes
        package_index.write(package_header.replace('PACKAGENAME', package_name))

        for class_name in extract_package_classes(package):
            print(class_name)
            substitutions = {
                'PACKAGE': package_name,
                'CLASS': class_name
            }
            class_template = template.substitute(**substitutions)
            class_rst = open(
                'api/{}/{}/{}.rst'.format(
                    qgis_version, package_name, class_name
                ), 'w'
            )
            print(class_template, file=class_rst)
            class_rst.close()
            package_index.write('   {}\n'.format(class_name))
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
        if class_name.startswith('_'):
            continue
        # if args.class_limit and not class_name.startswith(args.class_limit):
        #     continue
        # if not re.match('^Qgi?s', class_name):
        #     continue
        classes.append(class_name)

    return sorted(classes)


if __name__ == "__main__":
    generate_docs()
