from distutils.core import setup

setup(name='service-mgr',
      version='0.1.0',
      description='Asynchronous Service Manager for UNIX/Linux systems',
      author='Marin Atanasov Nikolov',
      author_email='dnaeon@gmail.com',
      license='BSD',
      packages=['service'],
      package_dir={'': 'src'},
      scripts=[
          'src/service-mgrd',
          'src/service-mgr-agentd',
          'src/service-mgr-client',
      ],
      install_requires=[
        'pyzmq >= 13.1.0',
        'docopt >= 0.6.1',
      ]
)

