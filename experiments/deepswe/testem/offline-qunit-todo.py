"""Four exact public assets, for the separately labelled todo diagnostic image."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('offline_qunit_base',
    Path(__file__).with_name('offline-qunit-base.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.PINS.update({
    '/qunit/qunit-2.9.2.js': ('qunit-2.9.2.js', 188837,
        '110e6bbfa90f14f29051863e3f81fa7e6fe57bec8544b5406ffff63df06cc1f1', 'application/javascript'),
    '/qunit/qunit-2.9.2.css': ('qunit-2.9.2.css', 7875,
        'b687a939ee43f9d757814386b228e78729999dae5b6a4274830442ff76cad5bd', 'text/css'),
})
PINS = base.PINS
load_assets = base.load_assets
allowed_request = base.allowed_request

if __name__ == '__main__':
    base.main()
