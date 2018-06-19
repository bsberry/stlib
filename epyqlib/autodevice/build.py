import collections
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import attr
import canmatrix.formats

import epyqlib.device


class InvalidAutoParametersDeviceError(Exception):
    pass


class MultipleFoundError(Exception):
    pass


@attr.s
class AccessInput:
    node = attr.ib()
    description = attr.ib()
    secret = attr.ib()
    value = attr.ib(default=None)


@attr.s
class Builder:
    access_parameters = attr.ib(default=None)
    required_serial_number = attr.ib(default=None)
    archive_code = attr.ib()
    _template = attr.ib(default=None, init=False)
    _template_path = attr.ib(default=None, init=False)
    _value_set = attr.ib(default=None, init=False)
    _target = attr.ib(default=None, init=False)

    @archive_code.default
    def _(self):
        code = epyqlib.utils.qt.get_code()
        if code is not None:
            code = code.decode('ascii')

        return code

    def set_access_level_names(self, password_name, access_level_name):
        self.access_parameters = (
            AccessInput(
                node=password_name,
                description='Elevated Access Code',
                secret=True,
            ),
            AccessInput(
                node=access_level_name,
                description='Elevated Access Level',
                secret=False,
            ),
        )

    def set_template(self, path):
        self._template_path = pathlib.Path(path)

        self._template = epyqlib.device.Device(
            file=os.fspath(self._template_path),
            only_for_files=True,
        )

        auto_value_set_key = 'auto_value_set'
        if auto_value_set_key not in self._template.raw_dict:
            raise InvalidAutoParametersDeviceError(
                'Key {} not found'.format(auto_value_set_key)
            )

    def load_pmvs(self, path):
        self._value_set = epyqlib.pm.valuesetmodel.loadp(path)

    def load_epp(self, parameter_path, can_path):
        matrix, = canmatrix.formats.loadp(can_path).values()
        neo = epyqlib.canneo.Neo(matrix=matrix)
        nvs = epyqlib.nv.Nvs(neo=neo)
        with open(parameter_path) as f:
            parameters = json.load(f)
        nvs.from_dict(parameters)
        self._value_set = nvs.to_value_set(include_secrets=True)

    def get_or_create_parameter(self, name):
        try:
            nodes = self._value_set.model.root.nodes_by_attribute(
                attribute_value=name,
                attribute_name='name',
            )
        except epyqlib.treenode.NotFoundError:
            node = epyqlib.pm.valuesetmodel.Parameter(
                name=name,
            )
            self._value_set.model.root.append_child(node)
        else:
            try:
                node, = nodes
            except ValueError as e:
                raise MultipleFoundError(
                    'Found multiple nodes but expected only one when '
                    'searching for {}'.format(repr(name))
                )

        return node

    def set_target(self, path):
        self._target = pathlib.Path(path)

    def create(self, original_raw_dict, can_contents):
        for access_input in self.access_parameters:
            access_input.node = self.get_or_create_parameter(access_input.node)

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_directory = pathlib.Path(temporary_directory)
            directory_path = temporary_directory / self._target.stem
            directory_path.mkdir()

            for access_input in self.access_parameters:
                node = self.get_or_create_parameter(name=access_input.node)

                node.value = access_input.value

            self._value_set.path = directory_path / self._template.raw_dict[
                'auto_value_set'
            ]
            self._value_set.save()

            can_path = self._template.raw_dict['can_path']

            for file_name in self._template.referenced_files:
                skips = (
                    can_path,
                    self._template.raw_dict['auto_value_set'],
                )
                if file_name in skips:
                    continue

                file_path = pathlib.Path(file_name)

                shutil.copy(
                    self._template_path.parent/file_path.name,
                    directory_path,
                )

            with open(self._template_path) as f:
                raw_dict = json.load(
                    f,
                    object_pairs_hook=collections.OrderedDict,
                )

            keys_to_copy = (
                'can_configuration',
                'nv_configuration',
                'node_id_type',
                'access_level_path',
                'access_password_path',
                'nv_meta_enum',
            )
            for key in keys_to_copy:
                raw_dict[key] = original_raw_dict[key]

            raw_dict['required_serial_number'] = self.required_serial_number

            can_path = directory_path / can_path
            with open(can_path, 'wb') as f:
                f.write(can_contents)

            matrix, = canmatrix.formats.loadp(os.fspath(can_path)).values()
            neo = epyqlib.canneo.Neo(
                matrix=matrix,
                frame_class=epyqlib.nv.Frame,
                signal_class=epyqlib.nv.Nv,
                strip_summary=False,
            )
            nvs = epyqlib.nv.Nvs(
                neo=neo,
                configuration=original_raw_dict['nv_configuration'],
            )

            serial_nv, = [
                nv
                for nv in nvs.all_nv()
                if (
                    'serial' in nv.name.casefold()
                    and 'number' in nv.name.casefold()
                )
            ]

            raw_dict['serial_number_names'] = (
                serial_nv.frame.mux_name,
                serial_nv.name,
            )

            target_epc_name = (
                directory_path / 'auto_parameters.epc'
            )
            with open(target_epc_name, 'w') as f:
                json.dump(raw_dict, f, indent=4)

            backup_path = None
            if self._target.exists():
                backup_path = temporary_directory / self._target.name
                shutil.move(self._target, backup_path)

            try:
                password_option = []
                if len(self.archive_code) > 0:
                    password_option = ['-p{}'.format(self.archive_code)]

                paths = (
                    pathlib.Path('7z'),
                    (
                        pathlib.Path('C:')
                        / os.sep
                        / 'Program Files'
                        / '7-Zip'
                        / '7z.exe',
                    ),
                    (
                        pathlib.Path('C:')
                        / os.sep
                        / 'Program Files (x86)'
                        / '7-Zip'
                        / '7z.exe',
                    ),
                )
                for path in paths:
                    try:
                        subprocess.run(
                            [
                                str(path),
                                'a',
                                '-tzip',
                                str(self._target),
                                str(directory_path),
                                *password_option,
                            ],
                            check=True,
                        )
                    except FileNotFoundError:
                        continue
                    else:
                        break
                else:
                    raise Exception(
                        'Unable to find 7z binary as any of: {}'.format(
                            paths,
                        )
                    )
            except Exception as e:
                if backup_path is not None:
                    shutil.move(backup_path, self._target)

                raise e
