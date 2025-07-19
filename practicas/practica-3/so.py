#!/usr/bin/env python

from hardware import *
import log
from enum import Enum
from collections import deque



## emulates a compiled program
class Program():

    def __init__(self, name, instructions):
        self._name = name
        self._instructions = self.expand(instructions)

    @property
    def name(self):
        return self._name

    @property
    def instructions(self):
        return self._instructions

    def addInstr(self, instruction):
        self._instructions.append(instruction)

    def expand(self, instructions):
        expanded = []
        for i in instructions:
            if isinstance(i, list):
                ## is a list of instructions
                expanded.extend(i)
            else:
                ## a single instr (a String)
                expanded.append(i)

        ## now test if last instruction is EXIT
        ## if not... add an EXIT as final instruction
        last = expanded[-1]
        if not ASM.isEXIT(last):
            expanded.append(INSTRUCTION_EXIT)

        return expanded

    def __repr__(self):
        return "Program({name}, {instructions})".format(name=self._name, instructions=self._instructions)


## emulates an Input/Output device controller (driver)
class IoDeviceController():

    def __init__(self, device):
        self._device = device
        self._waiting_queue = []
        self._currentPCB = None

    def runOperation(self, pcb, instruction):
        pair = {'pcb': pcb, 'instruction': instruction}
        # append: adds the element at the end of the queue
        self._waiting_queue.append(pair)
        # try to send the instruction to hardware's device (if is idle)
        self.__load_from_waiting_queue_if_apply()

    def getFinishedPCB(self):
        finishedPCB = self._currentPCB
        self._currentPCB = None
        self.__load_from_waiting_queue_if_apply()
        return finishedPCB

    def __load_from_waiting_queue_if_apply(self):
        if (len(self._waiting_queue) > 0) and self._device.is_idle:
            ## pop(): extracts (deletes and return) the first element in queue
            pair = self._waiting_queue.pop(0)
            #print(pair)
            pcb = pair['pcb']
            instruction = pair['instruction']
            self._currentPCB = pcb
            self._device.execute(instruction)


    def __repr__(self):
        return "IoDeviceController for {deviceID} running: {currentPCB} waiting: {waiting_queue}".format(deviceID=self._device.deviceId, currentPCB=self._currentPCB, waiting_queue=self._waiting_queue)

## emulates the  Interruptions Handlers
class AbstractInterruptionHandler():
    def __init__(self, kernel):
        self._kernel = kernel

    @property
    def kernel(self):
        return self._kernel

    def execute(self, irq):
        log.logger.error("-- EXECUTE MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))
    def runNextProgramCPUout(self):
        self.kernel.dispatcher.save()
        self.kernel.runningPCB = None
        if not self.kernel.readyQueue.isEmpty():
            pcb = self.kernel.readyQueue.dequeue()
            log.logger.info(HARDWARE)
            log.logger.info("\n Executing program: {name}".format(name=pcb.path))
            pcb.state = State.RUNNING
            self.kernel.runningPCB = pcb
            self.kernel.dispatcher.load(pcb)

    def runNextProgramCPUin(self, pcb):
        if not self.kernel.runningPCB:
            log.logger.info(HARDWARE)
            log.logger.info("\n Executing program: {name}".format(name=pcb.path))
            pcb.state = State.RUNNING
            self.kernel.runningPCB = pcb
            self.kernel.dispatcher.load(pcb)
        else:
            pcb.state = State.READY
            self.kernel.readyQueue.enqueue(pcb)

class NewInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        # Pedirle al loader que cargue el programa en memoria, y devuelva la baseDir
        program = irq.parameters
        baseDir = self.kernel.loader.load(program)
        # Crear el PCB, cargarle la baseDir
        pcb = PCB(self.kernel.pcbTable.getNewPID(), program.name, baseDir)
        # Cargar el PCB en la PCBTable, cambiando el estado a Ready
        self.kernel.pcbTable.add(pcb)
        self.runNextProgramCPUin(pcb)

class KillInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        log.logger.info(" Program Finished ")
        self.kernel.runningPCB.state = State.TERMINATED
        self.runNextProgramCPUout()

class IoInInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        operation = irq.parameters
        pcb = self.kernel.runningPCB
        self.kernel.dispatcher.save(pcb)
        pcb.state = State.WAITING
        self.kernel.ioDeviceController.runOperation(pcb, operation)
        log.logger.info(self.kernel.ioDeviceController)
        self.runNextProgramCPUout()

class IoOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        pcb = self.kernel.ioDeviceController.getFinishedPCB()
        log.logger.info(self.kernel.ioDeviceController)
        self.runNextProgramCPUin(pcb)

# emulates the core of an Operative System
class Kernel():

    def __init__(self):
        ## setup interruption handlers
        newHandler = NewInterruptionHandler(self)
        HARDWARE.interruptVector.register(NEW_INTERRUPTION_TYPE, newHandler)

        killHandler = KillInterruptionHandler(self)
        HARDWARE.interruptVector.register(KILL_INTERRUPTION_TYPE, killHandler)

        ioInHandler = IoInInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_IN_INTERRUPTION_TYPE, ioInHandler)

        ioOutHandler = IoOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(IO_OUT_INTERRUPTION_TYPE, ioOutHandler)

        ## controls the Hardware's I/O Device
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice)

        self._runningPCB = None

        self._pcbTable = PCBTable()
        self._loader = Loader()
        self._readyQueue = ReadyQueue()
        self._dispatcher = Dispatcher() 

    @property
    def ioDeviceController(self):
        return self._ioDeviceController

    ## emulates a "system call" for programs execution
    def run(self, program):
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, program)
        HARDWARE.interruptVector.handle(newIRQ)

    @property
    def runningPCB(self):
        return self._runningPCB
    
    @runningPCB.setter
    def runningPCB(self, pcb):
        self._runningPCB = pcb

    @property
    def pcbTable(self):
        return self._pcbTable
    
    @property
    def loader(self):
        return self._loader
    
    @property
    def readyQueue(self):
        return self._readyQueue
    
    @property
    def dispatcher(self):
        return self._dispatcher

    def __repr__(self):
        return "Kernel "
    
class State(Enum):
    NEW = 1
    READY = 2
    RUNNING = 3
    WAITING = 4
    TERMINATED = 5

class PCB():

    def __init__(self, pid, path, baseDir):
        self._pid = pid
        self._baseDir = baseDir
        self._pc = 0
        self._state = State.NEW
        self._path = path

    @property
    def pid(self):
        return self._pid
    
    @property
    def baseDir(self):
        return self._baseDir
    
    @property
    def state(self):
        return self._state
    
    @state.setter
    def state(self, newState):
        self._state = newState

    @property
    def pc(self):
        return self._pc

    @pc.setter
    def pc(self, newPc):
        self._pc = newPc

    @property
    def path(self):
        return self._path

class PCBTable():

    def __init__(self):
        self._table = {}
        self._incrVal = -1

    def get(self, pid):
        return self._table.get(pid)

    def add(self, pcb):
        self._table[pcb.pid] = pcb

    def remove(self, pid):
        del self._table[pid]

    def getNewPID(self):
        self._incrVal += 1
        return self._incrVal
    
class Dispatcher():

    def load(self, pcb):
        HARDWARE.cpu.pc = pcb.pc
        HARDWARE.mmu.baseDir = pcb.baseDir

    def save(self, pcb = None):
        if pcb:
            pcb.pc = HARDWARE.cpu.pc
        HARDWARE.cpu.pc = -1

class Loader():
    def __init__(self):
        self._availableDir = 0

    def load(self, program):
        baseDir = self._availableDir
        progSize = len(program.instructions)
        self._availableDir += progSize
        for index in range(baseDir, self._availableDir):
            inst = program.instructions[index - baseDir]
            HARDWARE.memory.write(index, inst)
        log.logger.info("\n Finished loading program: {name}".format(name=program.name))
        return baseDir

class ReadyQueue():

    def __init__(self):
        self._queue = deque()
    
    def enqueue(self, pcb):
        self._queue.append(pcb)

    def dequeue(self):
        return self._queue.popleft()
    
    def isEmpty(self):
        return len(self._queue) == 0
