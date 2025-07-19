#!/usr/bin/env python

from hardware import *
import log
from enum import Enum
from collections import deque

TICKSTOAGE = 4

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

    def _runPcb(self, pcb):
        log.logger.info(HARDWARE)
        log.logger.info("\n Executing program: {name}".format(name=pcb.path))
        pcb.state = State.RUNNING
        self.kernel.runningPCB = pcb
        self.kernel.dispatcher.load(pcb)

    def runNextProgramCPUout(self):
        self.kernel.dispatcher.save()
        self.kernel.runningPCB = None
        if not self.kernel.scheduler.isReadyQueueEmpty():
            pcb = self.kernel.scheduler.getNext()
            self._runPcb(pcb)

    def runNextProgramCPUin(self, pcb):
        if not self.kernel.runningPCB:
            self._runPcb(pcb)
        else:
            if(self.kernel.scheduler.mustExpropiate(self.kernel.runningPCB, pcb)):
                expropiatedPcb = self.kernel.runningPCB
                self.kernel.dispatcher.save(expropiatedPcb)
                expropiatedPcb.state = State.READY
                self.kernel.scheduler.add(expropiatedPcb)
                self._runPcb(pcb)
            else:
                pcb.state = State.READY
                self.kernel.scheduler.add(pcb)

class NewInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        parameters = irq.parameters
        program = parameters['program']
        priority = parameters['priority']
        # Pedirle al loader que cargue el programa en memoria, y devuelva la baseDir
        baseDir = self.kernel.loader.load(program)
        #burstTime = len(program.instructions) NO, porque las instrucciones tienen el formato ASM.CPU(3), eso cuenta como 1 con len() pero son 3.
        # Crear el PCB
        pcb = PCB(self.kernel.pcbTable.getNewPID(), program.name, baseDir, priority) #, burstTime)
        # Cargar el PCB en la PCBTable
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

class TimeOutInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        if not self.kernel.scheduler.isReadyQueueEmpty():
            expropiatedPcb = self.kernel.runningPCB
            self.kernel.dispatcher.save(expropiatedPcb)
            expropiatedPcb.state = State.READY
            pcb = self.kernel.scheduler.getNext()
            self.kernel.scheduler.add(expropiatedPcb)
            self._runPcb(pcb)

class StatInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        self.kernel.scheduler.checkTick(self.kernel)
        self.kernel.ganttDiagram.checkTick()
    
class State(Enum):
    NEW = 1
    READY = 2
    RUNNING = 3
    WAITING = 4
    TERMINATED = 5

class PCB():

    def __init__(self, pid, path, baseDir, priority):#, burstTime):
        self._pid = pid
        self._baseDir = baseDir
        self._pc = 0
        self._state = State.NEW
        self._path = path
        self._priority = priority
        #self._burstTime = burstTime

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
    
    @property
    def priority(self):
        return self._priority
    
    #@property
    #def burstTime(self):
    #    return self._burstTime

class PCBTable():

    def __init__(self):
        self._table = {}
        self._incrVal = -1

    def get(self, pid):
        return self._table.get(pid)
    
    def getAll(self):
        return {pid: pcb.state for pid, pcb in self._table.items()}

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
        HARDWARE.timer.reset()

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

class Scheduler():
    def __init__(self):
        self._readyQueue = []

    def add(self, pcb):
        log.logger.error("-- METHOD add() MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))

    def getNext(self):
        log.logger.error("-- METHOD getNext() MUST BE OVERRIDEN in class {classname}".format(classname=self.__class__.__name__))

    def isReadyQueueEmpty(self):
        return len(self._readyQueue) == 0
    
    def checkTick(self, kernel):
        pass

    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return False
    
class SchedulerFCFS(Scheduler):
    def __init__(self):
        self._readyQueue = deque()
    
    def add(self, pcb):
        self._readyQueue.append(pcb)

    def getNext(self):
        return self._readyQueue.popleft()

# class SchedulerSJFNoPreemptive(Scheduler):
#     def __init__(self):
#         self._readyQueue = []
    
#     def add(self, pcb):
#         # implementar algo como lo de abajo siendo burstTime la cantidad de instrucciones de cada programa
#         #self._readyQueue.append(pcb)
#         #self._readyQueue.sort(key = lambda p : p.burstTime)
#         pass

#     def getNext(self):
#        # descomentar lo de abajo si se pudo implementar lo de arriba
#        #return self._readyQueue.pop(0)
#        pass

# class SchedulerSJFPreemptive(SchedulerSJFNoPreemptive): 
#     def mustExpropiate(self, pcbInCPU, pcbToAdd):
#         # acá hay que implementar una lógica de comparación entre los pcb pasados por parámetro dependiendo del algoritmo
#         return False

class SchedulerPriorityNoPreemptive(Scheduler):

    def __init__(self):
        self._readyQueue = []
        self._ages = {}
        self._ticksToAge = TICKSTOAGE
    
    def add(self, pcb):
        self._readyQueue.append(pcb)
        self._ages[pcb.pid] = pcb.priority

    def getNext(self):
        self._readyQueue.sort(key = lambda p : self._ages[p.pid])
        return self._readyQueue.pop(0)

    def checkTick(self, kernel):
        if self._ticksToAge == 0:
            for key in self._ages:
                if kernel.pcbTable.get(key).state == State.READY and self._ages[key] > 0:
                    self._ages[key] -= 1

            self._ticksToAge = TICKSTOAGE
        else:
            self._ticksToAge -= 1

class SchedulerPriorityPreemptive(SchedulerPriorityNoPreemptive):

    def mustExpropiate(self, pcbInCPU, pcbToAdd):
        return pcbToAdd.priority < pcbInCPU.priority

class SchedulerRoundRobin(SchedulerFCFS):

    def __init__(self):
        super().__init__()
        HARDWARE.timer.quantum = 4

class GanttDiagram():
    
    def __init__(self, pcbTable):
        self._pcbTable = pcbTable
        self._ticksRegisters = []
        self._isOn = True

    def checkTick(self):
        if (self._isOn):
            currentTickData = {"tick" : HARDWARE.clock.currentTick}
            currentTickData.update(self._pcbTable.getAll())
            self._ticksRegisters.append(currentTickData)
            # Si todos los procesos terminaron
            if all(state == State.TERMINATED for state in self._pcbTable.getAll().values()):
                self.printGanttDiagram(currentTickData.keys())
                self._isOn = False

    def printGanttDiagram(self, headers):
        stateNotation = {
            State.READY : '*',
            State.WAITING : 'W',
            State.TERMINATED : '-',
            State.RUNNING: 'R'
        }
        rows = []
        for tick in self._ticksRegisters:
            row = [stateNotation.get(value, value) for value in tick.values()]
            rows.append(row)
        
        log.logger.info(tabulate(rows, headers=headers, tablefmt="grid"))

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

        timeoutHandler = TimeOutInterruptionHandler(self)
        HARDWARE.interruptVector.register(TIMEOUT_INTERRUPTION_TYPE, timeoutHandler)

        statInterruptionHandler = StatInterruptionHandler(self)
        HARDWARE.interruptVector.register(STAT_INTERRUPTION_TYPE, statInterruptionHandler)

        ## controls the Hardware's I/O Device
        self._ioDeviceController = IoDeviceController(HARDWARE.ioDevice)

        self._runningPCB = None

        self._pcbTable = PCBTable()
        self._loader = Loader()
        self._dispatcher = Dispatcher()
        HARDWARE.cpu.enable_stats = True
        self._ganttDiagram = GanttDiagram(self._pcbTable)
        # self._scheduler = SchedulerFCFS()
        # self._scheduler = SchedulerPriorityNoPreemptive()
        # self._scheduler = SchedulerPriorityPreemptive()
        self._scheduler = SchedulerRoundRobin()

    @property
    def ioDeviceController(self):
        return self._ioDeviceController

    ## emulates a "system call" for programs execution
    def run(self, program, priority):
        parameters = {'program': program, 'priority': priority}
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, parameters)
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
    def scheduler(self):
        return self._scheduler

    @property
    def dispatcher(self):
        return self._dispatcher
    
    @property
    def ganttDiagram(self):
        return self._ganttDiagram

    def __repr__(self):
        return "Kernel "