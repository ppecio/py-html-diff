from distutils.core import setup

setup(
    name='py-html-diff',
    version='0.1',
    packages=['pyhtmldiff', 'differ', 'dtd', 'producer'],
    package_dir={
        'pyhtmldiff': 'pyhtmldiff',
        'differ': 'pyhtmldiff/differ',
        'dtd': 'pyhtmldiff/dtd',
        'producer': 'pyhtmldiff/producer',
    },
    url='',
    license='Apache',
    author='Pawel Pecio',
    author_email='ppecio@nglogic.com',
    description='',
    install_requires=[
        'genshi',
        'html5lib',
        'flufl.enum'
    ],
)
