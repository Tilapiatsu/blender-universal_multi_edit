# Unit testing template for Blender add-ons
# Copyright (C) 2025 Spencer Magnusson

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import unittest
import importlib.util


class TestAddon(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Install add-on"""
        from tests.scripts import get_script
        from tests.manifest_info import get_manifest_info

        zip_main = get_script("zip_addon").zip_main

        manifest = get_manifest_info()
        cls.zip_path = zip_main(manifest["id"])
        if cls.zip_path is None:
            raise Exception("Failed to create zip file")

        import bpy

        bpy.ops.preferences.addon_install(filepath=cls.zip_path)
        bpy.ops.preferences.addon_enable(module=manifest["id"])

    def setUp(self):
        """Run homefile, resetting the file"""
        import bpy

        bpy.ops.wm.read_homefile()

    def test_disable_enable(self):
        """Validate enabling or disabling the add-on"""
        from tests.manifest_info import get_manifest_info

        manifest = get_manifest_info()
        try:
            import bpy

            bpy.ops.preferences.addon_disable(module=manifest["id"])
            bpy.ops.preferences.addon_enable(module=manifest["id"])
        except Exception as e:
            self.fail(str(e))

    @classmethod
    def tearDownClass(cls):
        """Uninstall add-on"""
        import bpy
        from tests.manifest_info import get_manifest_info

        manifest = get_manifest_info()

        bpy.ops.preferences.addon_disable(module=manifest["id"])

        import os
        import shutil

        os.unlink(cls.zip_path)

        # get folder of addon_testing, remove folder
        # import addon_testing
        # installed_addon_folder = os.path.dirname(addon_testing.__file__)
        # print('Removing ' + installed_addon_folder + '...')
        # shutil.rmtree(installed_addon_folder)
