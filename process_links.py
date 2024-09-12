# This scripts provides formatting for signature and docstrings to create links
# Links are not rendered in signatures: https://github.com/sphinx-doc/sphinx/issues/1059
# Also, sadly we cannot use existing extension autodoc-auto-typehints
# since __annotations__ are not filled in QGIS API, obviously because of SIP
#
# This logic has been copied from the existing extension with some tuning for PyQGIS

import enum
import re

import yaml

from documenters import create_links, inject_args

with open("pyqgis_conf.yml") as f:
    cfg = yaml.safe_load(f)


# https://github.com/sphinx-doc/sphinx/blob/685e3fdb49c42b464e09ec955e1033e2a8729fff/sphinx/ext/autodoc/__init__.py#L51
# adapted to handle signals

# https://regex101.com/r/lSB3rK/2/
py_ext_sig_re = re.compile(
    r"""^ ([\w.]+::)?            # explicit module name
          ([\w.]+\.)?            # module and/or class name(s)
          (\w+)  \s*             # thing name
          (?: \((.*)\)          # optional: arguments
          (?:\s* -> \s* ([\w.]+(?:\[.*?\])?))?   # return annotation
          (?:\s* \[(signal)\])?    # is signal
          )? $                   # and nothing more
          """,
    re.VERBOSE,
)


def process_docstring(app, what, name, obj, options, lines):
    if what == "class":
        # hacky approach to detect nested classes, eg QgsCallout.QgsCalloutContext
        is_nested = len(name.split(".")) > 3
        if not is_nested:
            # remove docstring part, we've already included it in the page header
            # only leave the __init__ methods
            init_idx = 0
            class_name = name.split(".")[-1]
            for init_idx, line in enumerate(lines):
                if re.match(rf"^{class_name}\(", line):
                    break

            lines[:] = lines[init_idx:]
            lines_out = []
            # loop through remaining lines, which are the constructors. Format
            # these up so they look like proper __init__ method documentation
            for i, line in enumerate(lines):
                if re.match(rf"^{class_name}\(", line):
                    lines_out.append(
                        re.sub(rf"\b{class_name}\(", ".. py:method:: __init__(", line)
                    )
                    lines_out.append("    :noindex:")
                    lines_out.append("")
                else:
                    lines_out.append("    " + line)

            lines[:] = lines_out[:]
            return

    for i in range(len(lines)):
        # fix seealso
        # lines[i] = re.sub(r':py: func:`(\w+\(\))`', r':func:`.{}.\1()'.format(what), lines[i])
        lines[i] = create_links(lines[i])

    if what == "attribute":
        from documenters import SipAttributeDocumenter

        print(name)
        print(SipAttributeDocumenter.parent_obj)
        try:
            args = SipAttributeDocumenter.parent_obj.__signal_arguments__.get(
                name.split(".")[-1], []
            )
            inject_args(args, lines)
        except AttributeError:
            pass
    # add return type and param type
    elif what != "class" and not isinstance(obj, enum.EnumMeta) and obj.__doc__:
        # default to taking the signature from the lines we've already processed.
        # This is because we want the output processed earlier via the
        # OverloadedPythonMethodDocumenter class, so that we are only
        # looking at the docs relevant to the specific overload we are
        # currently processing
        signature = None
        match = None
        if lines:
            signature = lines[0]
        if signature:
            match = py_ext_sig_re.match(signature)
            if match:
                del lines[0]

        if match is None:
            signature = obj.__doc__.split("\n")[0]
            if signature == "":
                return
            match = py_ext_sig_re.match(signature)

        if match is None:
            if name not in cfg["non-instantiable"]:
                raise Warning(f"invalid signature for {name}: {signature}")

        else:
            exmod, path, base, args, retann, signal = match.groups()

            if args:
                args = args.split(", ")
                inject_args(args, lines)

            if retann:
                insert_index = len(lines)
                for i, line in enumerate(lines):
                    if line.startswith(":rtype:"):
                        insert_index = None
                        break
                    elif line.startswith(":return:") or line.startswith(":returns:"):
                        insert_index = i

                if insert_index is not None:
                    if insert_index == len(lines):
                        # Ensure that :rtype: doesn't get joined with a paragraph of text, which
                        # prevents it being interpreted.
                        lines.append("")
                        insert_index += 1

                    lines.insert(insert_index, f":rtype: {create_links(retann)}")


def process_signature(app, what, name, obj, options, signature, return_annotation):
    # we cannot render links in signature for the moment, so do nothing
    # https://github.com/sphinx-doc/sphinx/issues/1059
    return signature, return_annotation


def skip_member(app, what, name, obj, skip, options):
    # skip monkey patched enums (base classes are different)
    if name == "staticMetaObject":
        return True
    if name == "baseClass":
        return True
    if hasattr(obj, "is_monkey_patched") and obj.is_monkey_patched:
        # print(f"skipping monkey patched enum {name}")
        return True
    return skip


def process_bases(app, name, obj, option, bases: list) -> None:
    """Here we fine tune how the base class's classes are displayed."""
    for i, base in enumerate(bases):
        # replace 'sip.wrapper' base class with 'object'
        if base.__name__ == "wrapper":
            bases[i] = object
