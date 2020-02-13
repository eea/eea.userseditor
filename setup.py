import os
from setuptools import setup, find_packages

NAME = "eea.userseditor"
PATH = NAME.split('.') + ['version.txt']
VERSION = open(os.path.join(*PATH)).read().strip()

setup(name=NAME,
      version=VERSION,
      description="EEA Users Editor",
      long_description_content_type="text/x-rst",
      long_description=(
          open("README.rst").read() + "\n" +
          open("CHANGELOG.rst").read()
      ),
      author='Eau de Web',
      author_email='office@eaudeweb.ro',
      packages=find_packages(),
      include_package_data=True,
      platforms=['OS Independent'],
      zip_safe=False,
      install_requires=['eea.usersdb>=1.3.40', 'deform', 'phonenumbers',
                        'six'],
      )
