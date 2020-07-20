from setuptools import setup

def readme():
    with open('README.md') as f:
        return f.read()

setup(name='pyhomie',
      version='0.1',
      description='Homie Convention implementation',
      long_description='An extensible implementation of the Homie Convention',
      url='https://github.com/bggardner/pyhomie',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Apache Software License',
          'Programming Language :: Python :: 3 :: Only',
          'Topic :: Software Development :: Libraries :: Python Modules'
      ],
      author='Brent Gardner',
      author_email='brent@ebrent.net',
      license='Apache 2.0',
      packages=['pyhomie'],
      install_requires=[
          'paho-mqtt>=1.4'
      ],
      include_package_data=True,
      zip_safe=False)
