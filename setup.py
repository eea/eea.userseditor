from setuptools import setup, find_packages

setup(name='eea.userseditor',
      version='1.1.15',
      author='Eau de Web',
      author_email='office@eaudeweb.ro',
      packages=find_packages(),
      include_package_data=True,
      platforms=['OS Independent'],
      zip_safe=False,
      install_requires=['eea.usersdb>=1.3.12', 'deform', 'phonenumbers'],
      )
