from hardware import *
from so import *
import log


##
##  MAIN 
##
if __name__ == '__main__':
    log.setupLogger()
    log.logger.info('Starting emulator')

    ## setup our hardware and set memory size to 2 "cells"
    HARDWARE.setup(20)

    ## new create the Operative System Kernel
    # "booteamos" el sistema operativo
    kernel = Kernel()

    prg1 = Program([ASM.CPU(2), ASM.IO(), ASM.CPU(3), ASM.IO(), ASM.CPU(2)])
    prg2 = Program([ASM.CPU(7)])
    prg3 = Program([ASM.CPU(4), ASM.IO(), ASM.CPU(1)])

    kernel.fileSystem.write("C:/prg1.exe", prg1)
    kernel.fileSystem.write("C:/prg2.exe", prg2)
    kernel.fileSystem.write("C:/prg3.exe", prg3)

    kernel.run("C:/prg1.exe", 0)
    kernel.run("C:/prg2.exe", 2)
    kernel.run("C:/prg3.exe", 1)

    ## Switch on computer
    HARDWARE.switchOn()



