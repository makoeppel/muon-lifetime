# README #

### DRS4 Evaluation Board firmware and software ###

* VHDL firmware for Xilinx ISE
* **drscl** command line interface to DRS4 Evaluation Board
* **drsosc** oscilloscope program for DRS4 Evaluation Board

### Build ###

* clone repository recursively:

```git clone https://bitbucket.org/ritt/drs4eb.git --recursive```

* Install wxWidgets from https://www.wxwidgets.org/ (only if DRSOsc program is needed). Make sure the ``wx-config`` tool is working.

* Build executables:

```
$ cd drs4eb/software
$ mkdir build
$ cd build
$ cmake ..
$ make
```

* Build "drscl" program only:

``` 
$ makde drscl
```

### Contact ###

Stefan Ritt <stefan.ritt@psi.ch>