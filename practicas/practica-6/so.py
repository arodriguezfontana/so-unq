#!/usr/bin/env python

from hardware import *
import log
from enum import Enum
from collections import deque

TICKSTOAGE = 4

## emulates a compiled program
class Program():

    def __init__(self, instructions):
        self._instructions = self.expand(instructions)

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
        return "Program({instructions})".format(instructions=self._instructions)


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
        path = parameters['path']
        priority = parameters['priority']
        pageTable = self.kernel.loader.load(path)
        if (pageTable == -1):
            return
        pcb = PCB(self.kernel.pcbTable.getNewPID(), path, priority, pageTable)
        self.kernel.pcbTable.add(pcb)
        self.runNextProgramCPUin(pcb)

class KillInterruptionHandler(AbstractInterruptionHandler):

    def execute(self, irq):
        log.logger.info(" Program Finished ")
        pcbToKill = self.kernel.runningPCB
        pcbToKill.state = State.TERMINATED
        self.kernel.memoryManager.freeFrames(pcbToKill.pageTable)
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

    def __init__(self, pid, path, priority, pageTable):
        self._pid = pid
        self._pc = 0
        self._state = State.NEW
        self._path = path
        self._priority = priority
        self._pageTable = pageTable

    @property
    def pid(self):
        return self._pid
    
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
    
    @property
    def pageTable(self):
        return self._pageTable
    
    @pageTable.setter
    def pageTable(self, newTable):
        self._pageTable = newTable

class PCBTable():

    def __init__(self, kernel):
        self._table = {}
        self._incrVal = -1
        self._kernel = kernel

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
    
    def compact(self):
        interruptedPCB = self.kernel.runningPCB
        self.kernel.dispatcher.save(self.kernel.runningPCB)
        interruptedPCB.state = State.READY

        pcbList = list(self._table.values())
        sortedTable = sorted(pcbList, key=lambda pcb: pcb.baseDir)
        offset = 0

        for pcb in sortedTable:
            displacement = pcb.baseDir - offset
            pcb.baseDir -= displacement
            pcb.pc -= displacement
            pcb.limitDir -= displacement
            offset = pcb.limitDir + 1

        self.kernel.dispatcher.load(interruptedPCB)
        interruptedPCB.state = State.RUNNING

    @property
    def kernel(self):
        return self._kernel
    
class Dispatcher():

    def load(self, pcb):
        HARDWARE.mmu.resetTLB()

        for page, frame in enumerate(pcb.pageTable):
            HARDWARE.mmu.setPageFrame(page, frame)
        
        HARDWARE.cpu.pc = pcb.pc
        HARDWARE.timer.reset()

    def save(self, pcb = None):
        if pcb:
            pcb.pc = HARDWARE.cpu.pc
        HARDWARE.cpu.pc = -1

class Loader():
    def __init__(self, memoryManager, fileSystem, frameSize):
        self._memoryManager = memoryManager
        self._fileSystem = fileSystem
        self._frameSize = frameSize
    
    def __createPageTable(self, availableFrames, program, progSize, path):
        pageTable = []
        for frameId in availableFrames:
            pageTable.append(frameId)
            offset = 0
            logicalAddress = (len(pageTable) - 1) * self._frameSize  + offset
            while(offset < self._frameSize and logicalAddress < progSize):
                inst = program.instructions[logicalAddress]
                physicalAddress = frameId * self._frameSize + offset
                log.logger.info("Se va a cargar la instruccion {l} en {p}".format(l = logicalAddress, p = physicalAddress))
                HARDWARE.memory.write(physicalAddress, inst)
                offset += 1
                logicalAddress = (len(pageTable) - 1) * self._frameSize  + offset
        log.logger.info("\n Finished loading program: {name}".format(name=path))
        return pageTable

    def load(self, path):
        program = self._fileSystem.read(path)
        progSize = len(program.instructions)
        pagesQuantity = progSize // self._frameSize
        if (progSize % self._frameSize > 0):
            pagesQuantity += 1
        availableFrames = self._memoryManager.allocFrames(pagesQuantity)
        if (not availableFrames):
            log.logger.info("\n Program: {name} couldn't be loaded".format(name=path))
            return -1       
        return self.__createPageTable(availableFrames, program, progSize, path)

    @property
    def memoryManager(self):
        return self._memoryManager

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
            # If every process has ended
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

class Crontab():

    def __init__(self, kernel):
        self._jobs = {}
        self._kernel = kernel
        HARDWARE.clock.addSubscriber(self)

    def add_job(self, tickNbr, path, priority):
        job = {'path': path, 'priority': priority}
        self._jobs[tickNbr] = job
        log.logger.info("Crontab: add job {job} to Tick {tickNbr} ".format(job = job, tickNbr = tickNbr))

    def tick(self, tickNbr):
        job = self._jobs.get(tickNbr)
        if job != None:
            log.logger.info("Tick {tickNbr} - Running job: {job}".format(job = job, tickNbr = tickNbr))
            self.run_job(job)

    def run_job(self, job):
        path = job['path']
        priority = job['priority']
        self._kernel.run(path, priority)

class MemoryManager():

    def __init__(self, memorySize, kernel, frameSize):
        self._kernel = kernel
        self._memorySize = memorySize
        self._freeSize = memorySize
        self._frameSize = frameSize
        self._frames = list(range(memorySize // frameSize))

    def allocFrames(self, quantity):
        if (quantity > len(self._frames)):
            log.logger.info("There's not enough frames available")
            return False
        allocatedFrames, self._frames = self._frames[:quantity], self._frames[quantity:]
        self._freeSize -= len(allocatedFrames) * self._frameSize
        return allocatedFrames
    
    def freeFrames(self, framesToFree):
        self._freeSize += len(framesToFree) * self._frameSize
        self._frames.extend(framesToFree)

    @property
    def kernel(self):
        return self._kernel
    
class FileSystem():

    def __init__(self):
        self._fileSystem = dict()
    
    def write(self, path, program):
        self._fileSystem[path] = program

    def read(self, path):
        return self._fileSystem.get(path)

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

        HARDWARE.mmu.frameSize = 4
        self._pcbTable = PCBTable(self)
        # self._memoryManager = MemoryManager(HARDWARE.memory.size, self, FirstFitAlgorithm()) #FirstFitAlgorithm
        # self._memoryManager = MemoryManager(HARDWARE.memory.size, self, WorstFitAlgorithm()) #WorstFitAlgorithm
        self._memoryManager = MemoryManager(HARDWARE.memory.size, self, HARDWARE.mmu.frameSize) #BestFitAlgorithm
        self._fileSystem = FileSystem()
        self._loader = Loader(self._memoryManager, self._fileSystem, HARDWARE.mmu.frameSize)
        self._dispatcher = Dispatcher()
        HARDWARE.cpu.enable_stats = True
        self._ganttDiagram = GanttDiagram(self._pcbTable)
        # self._scheduler = SchedulerFCFS()
        # self._scheduler = SchedulerPriorityNoPreemptive()
        # self._scheduler = SchedulerPriorityPreemptive()
        self._scheduler = SchedulerRoundRobin()

        self._crontab = Crontab(self)

    @property
    def ioDeviceController(self):
        return self._ioDeviceController

    ## emulates a "system call" for programs execution
    def run(self, path, priority):
        parameters = {'path': path, 'priority': priority}
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
    
    @property
    def memoryManager(self):
        return self._memoryManager
    
    @property
    def crontab(self):
        return self._crontab
    
    @property
    def fileSystem(self):
        return self._fileSystem

    def __repr__(self):
        return "Kernel "