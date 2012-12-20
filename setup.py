from distutils.core import setup

package_dir = {'ape': 'src/ape'}

setup(
    name='ape',
    version='2012.12.19.17',
    author='Jonathan Newbrough',
    author_email='jonathan.newbrough@gyregroup.com',
    url='https://github.com/ooici/ape',
    package_dir = {'': 'src'},
    packages=['ape', 'ape.agent', 'ape.common', 'ape.component'],
)
