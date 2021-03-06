########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import agent_packager.packager as ap
import agent_packager.utils as utils
from agent_packager.logger import init
from requests import ConnectionError

from contextlib import closing
from testfixtures import log_capture
import logging
import tarfile
import testtools
import os
import shutil
from functools import wraps


TEST_RESOURCES_DIR = 'agent_packager/tests/resources/'
CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'config_file.yaml')
BAD_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'bad_config_file.yaml')
EMPTY_CONFIG_FILE = os.path.join(TEST_RESOURCES_DIR, 'empty_config_file.yaml')
BASE_DIR = 'cloudify/test_venv'
TEST_VENV = os.path.join(BASE_DIR, 'env')
TEST_MODULE = 'xmltodict'
TEST_FILE = 'https://github.com/cloudify-cosmo/cloudify-agent-packager/archive/master.tar.gz'  # NOQA
MANAGER = 'https://github.com/cloudify-cosmo/cloudify-manager/archive/master.tar.gz'  # NOQA


def venv(func):
    @wraps(func)
    def execution_handler(*args, **kwargs):
        utils.make_virtualenv(TEST_VENV)
        func(*args, **kwargs)
        shutil.rmtree(TEST_VENV)
    return execution_handler


class TestBase(testtools.TestCase):

    @log_capture()
    def test_set_global_verbosity_level(self, capture):
        lgr = init(base_level=logging.INFO)

        ap._set_global_verbosity_level(is_verbose_output=False)
        lgr.debug('TEST_LOGGER_OUTPUT')
        capture.check()
        lgr.info('TEST_LOGGER_OUTPUT')
        capture.check(('user', 'INFO', 'TEST_LOGGER_OUTPUT'))

        ap._set_global_verbosity_level(is_verbose_output=True)
        lgr.debug('TEST_LOGGER_OUTPUT')
        capture.check(
            ('user', 'INFO', 'TEST_LOGGER_OUTPUT'),
            ('user', 'DEBUG', 'TEST_LOGGER_OUTPUT'))

    def test_import_config_file(self):
        outcome = ap._import_config(CONFIG_FILE)
        self.assertEquals(type(outcome), dict)
        self.assertIn('distribution', outcome.keys())

    def test_fail_import_config_file(self):
        e = self.assertRaises(RuntimeError, ap._import_config, '')
        self.assertEquals('cannot access config file', str(e))

    def test_import_bad_config_file_mapping(self):
        e = self.assertRaises(Exception, ap._import_config, BAD_CONFIG_FILE)
        self.assertIn('mapping values are not allowed here', str(e))

    def test_import_bad_config_file(self):
        e = self.assertRaises(Exception, ap._import_config, BAD_CONFIG_FILE)
        self.assertIn('mapping values are not allowed here', str(e))

    def test_run(self):
        p = utils.run('uname')
        self.assertEqual(0, p.returncode)

    def test_run_bad_command(self):
        p = utils.run('suname')
        self.assertEqual(127, p.returncode)

    @venv
    def test_create_virtualenv(self):
        if not os.path.exists('{0}/bin/python'.format(TEST_VENV)):
            raise Exception('venv not created')

    def test_fail_create_virtualenv_bad_dir(self):
        e = self.assertRaises(
            SystemExit, utils.make_virtualenv, '/' + TEST_VENV)
        self.assertEqual('1', str(e))

    def test_fail_create_virtualenv_missing_python(self):
        e = self.assertRaises(
            SystemExit, utils.make_virtualenv, TEST_VENV,
            '/usr/bin/missing_python')
        self.assertEqual('1', str(e))

    @venv
    def test_install_module(self):
        utils.install_module(TEST_MODULE, TEST_VENV)
        p = utils.run('{0}/bin/pip freeze'.format(TEST_VENV))
        self.assertIn(TEST_MODULE, p.stdout)

    @venv
    def test_install_nonexisting_module(self):
        e = self.assertRaises(
            SystemExit, utils.install_module, 'BLAH!!', TEST_VENV)
        self.assertEqual('2', str(e))

    def test_install_module_nonexisting_venv(self):
        e = self.assertRaises(
            SystemExit, utils.install_module, TEST_MODULE, 'BLAH!!')
        self.assertEqual('2', str(e))

    def test_download_file(self):
        utils.download_file(TEST_FILE, 'file')
        if not os.path.isfile('file'):
            raise Exception('file not downloaded')
        os.remove('file')

    def test_download_file_missing(self):
        e = self.assertRaises(
            SystemExit, utils.download_file,
            'http://www.google.com/x.tar.gz', 'file')
        self.assertEqual('3', str(e))

    def test_download_bad_url(self):
        e = self.assertRaises(
            Exception, utils.download_file, 'something', 'file')
        self.assertIn('Invalid URL', str(e))

    def test_download_connection_failed(self):
        e = self.assertRaises(
            ConnectionError, utils.download_file, 'http://something', 'file')
        self.assertIn('Connection aborted', str(e))

    def test_download_missing_path(self):
        e = self.assertRaises(
            IOError, utils.download_file, TEST_FILE, 'x/file')
        self.assertIn('No such file or directory', e)

    def test_download_no_permissions(self):
        e = self.assertRaises(IOError, utils.download_file, TEST_FILE, '/file')
        self.assertIn('Permission denied', e)

    @venv
    def test_download_manager_code(self):
        d = ap._get_manager(MANAGER, TEST_VENV)
        self.assertTrue(os.path.isdir(
            os.path.join(d, 'plugins/plugin-installer')))
        self.assertTrue(os.path.isdir(
            os.path.join(d, 'plugins/agent-installer')))
        self.assertTrue(os.path.isdir(
            os.path.join(d, 'plugins/windows-plugin-installer')))
        self.assertTrue(os.path.isdir(
            os.path.join(d, 'plugins/windows-agent-installer')))
        shutil.rmtree(d)

    def test_tar(self):
        os.makedirs('dir')
        with open('dir/content.file', 'w') as f:
            f.write('CONTENT')
        utils.tar('dir', 'tar.file')
        shutil.rmtree('dir')
        self.assertTrue(tarfile.is_tarfile('tar.file'))
        with closing(tarfile.open('tar.file', 'r:gz')) as tar:
            members = tar.getnames()
            self.assertIn('dir/content.file', members)
        os.remove('tar.file')

    @venv
    def test_tar_no_permissions(self):
        e = self.assertRaises(SystemExit, utils.tar, TEST_VENV, '/file')
        self.assertIn(str(e), '10')

    @venv
    def test_tar_missing_source(self):
        e = self.assertRaises(SystemExit, utils.tar, 'missing', 'file')
        self.assertIn(str(e), '10')
        os.remove('file')

    def test_create_agent_package(self):
        config = ap._import_config(CONFIG_FILE)
        ap.create(None, CONFIG_FILE, force=True, verbose=True)
        if os.path.isdir(config['venv']):
            raise Exception('venv exists before extracting agent.')
        os.makedirs(config['venv'])
        utils.run('tar -xzvf {0} -C {1} --strip-components=2'.format(
            config['output_tar'], BASE_DIR))
        os.remove(config['output_tar'])
        self.assertTrue(os.path.isdir(config['venv']))
        p = utils.run('{0}/bin/pip freeze'.format(config['venv']))
        self.assertIn('cloudify-plugins-common', p.stdout)
        self.assertIn('cloudify-rest-client', p.stdout)
        self.assertIn('cloudify-script-plugin', p.stdout)
        self.assertIn('cloudify-diamond-plugin', p.stdout)
        shutil.rmtree(config['venv'])

    @venv
    def test_create_agent_package_existing_venv_no_force(self):
        e = self.assertRaises(
            SystemExit, ap.create, None, CONFIG_FILE, verbose=True)
        self.assertEqual(str(e), '2')

    @venv
    def test_create_agent_package_tar_already_exists(self):
        config = ap._import_config(CONFIG_FILE)
        shutil.rmtree(config['venv'])
        with open(config['output_tar'], 'w') as a:
            a.write('CONTENT')
        e = self.assertRaises(
            SystemExit, ap.create, None, CONFIG_FILE, verbose=True)
        self.assertEqual(str(e), '9')
        os.remove(config['output_tar'])
