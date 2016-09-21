from setuptools import setup


setup(
    name='scraper_lib',
    packages=['scraper_lib'],
    version='1.0.1',
    description='Platform specific scrapers',
    author='Eddy Hintze',
    author_email="eddy.hintze@gmail.com",
    url="https://github.com/xtream1101/scraper-lib",
    license='MIT',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    install_requires=[
        'cutil',
        'bs4',
        'minio',
        'pillow',
        'requests',
        'selenium',
        'fake_useragent',
    ],
)
