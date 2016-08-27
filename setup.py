from setuptools import setup


setup(
    name='scraper_lib',
    packages=['scrapers'],
    version='1.0.1',
    description='Platform specific scrapers',
    author='Eddy Hintze',
    author_email="eddy.hintze@gmail.com",
    url="https://git.eddyhintze.com/xtream1101/scraper-lib",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: MIT",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    dependency_links = [
        'git+https://github.com/xtream1101/custom-utils.git@master#egg=custom_utils',
        'git+https://github.com/xtream1101/scraper-monitor-lib@master#egg=scraper_monitor'
    ],
    install_requires=[
        'custom_utils',
        'scraper_monitor',
        'minio',
        'requests',
        'selenium',
        'fake_useragent',
    ],
)
