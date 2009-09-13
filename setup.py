from setuptools import setup, find_packages
import sys, os

version = '0.1a2'

setup(name='strainer',
      version=version,
      description="Tools to alloww developers to cleanup web serialization objects (HTML, JSON, XHTML)",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='html json wsgi',
      author='Tom Lynn and Chris Perkins',
      author_email='chris@percious.com',
      url='',
      license='MIT',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=True,
      install_requires=[
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
