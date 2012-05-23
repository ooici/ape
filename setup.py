from distutils.core import setup

package_dir = {'ape': 'src/ape'}

setup(name='ape',
    version='2012.5.22',
    author='Jonathan Newbrough',
    author_email='jonathan.newbrough@gyregroup.com',
    url='https://github.com/ooici/ape',
    package_dir = {'': 'src'},
#    py_packages=['ape.agent', 'ape.common', 'ape.component'],
    packages=['ape', 'ape.agent', 'ape.common', 'ape.component'],
)