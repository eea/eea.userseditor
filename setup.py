''' installer for eea.userseditor '''
from os.path import join
from setuptools import setup, find_packages

NAME = "eea.userseditor"
PATH = NAME.split('.') + ['version.txt']
VERSION = open(join(*PATH)).read().strip()

setup(name=NAME,
      version=VERSION,
      description="EEA Users Editor",
      long_description_content_type="text/x-rst",
      long_description=(
          open("README.rst").read() + "\n" +
          open(join("docs", "HISTORY.txt")).read()
      ),
      author='Eau de Web',
      author_email='office@eaudeweb.ro',
      packages=find_packages(),
      include_package_data=True,
      platforms=['OS Independent'],
      zip_safe=False,
      install_requires=[
          'eea.usersdb>=2.6',
          'deform',
          'phonenumbers',
          'six'
      ],
      extras_require={
          'test': [
              'eea.ldapadmin>=2.8',
          ],
      },
      )
