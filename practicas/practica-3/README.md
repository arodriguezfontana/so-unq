# Práctica 3
## Multiprogramación


En esta versión, la __CPU__ no accede directamente a la __Memoria__, como hace la __CPU__ para fetchear la instruccion?? Por que??

Existe un componente de hardware llamado Memory Management Unit (__MMU__) que se encarga de transformar las direcciones lógicas (relativas)  en direcciones físicas (absolutas)



## Interrupciones de I/O y Devices

En esta version del emulador agregamos los I/O Devices y el manejo de los mismos

Un I/O device es un componente de hardware (interno o externo) que realiza operaciones específicas.

Una particularidad que tienen estos dispositivos es los tiempos de ejecucion son mas extensos que los de CPU, ej: bajar un archivo de internet, imprimir un archivo, leer desde un DVD, etc.
Por otro lado, solo pueden ejecutar una operacion a la vez, con lo cual nuestro S.O. debe garantizar que no se "choquen" los pedidos de ejecucion.

Para ello implementamos un __IoDeviceController__ que es el encargado de "manejar" el device, encolando los pedidos para ir sirviendolos a medida que el dispositivo se libere.


También se incluyeron 2 interrupciones 

- __#IO_IN__
- __#IO_OUT__



## Lo que tenemos que hacer es:

- __1:__ Describir como funciona el __MMU__ y que datos necesitamos para correr un proceso

    ```
    La MMU (Memory Management Unit) transforma las direcciones lógicas en direcciones físicas con el
    objetivo de saber donde hacer el fetch en memoria de la próxima instrucción del proceso que está
    ejecutándose. Esto es posible almacenando la dirección base (BaseDir) del proceso en ejecución y
    sumándole su program counter (PC). Dicha suma, devuelve la dirección física en la que se encuentra
    la siguiente instrucción a ejecutar.
    Para correr un proceso se necesitan los siguientes datos:
    * PC: Indica por que instrucción se encuentra el programa. Si no se ejecutó antes, el pc = 0.
    * BaseDir: La dirección de memoria en la que se encuentra alojada la primera instrucción del programa.
    Ambos datos se encuentran en el PCB del proceso, junto con su identificador único (pid), path y state 
    entre otros. Si vamos a detalle, el pid siempre es necesario, ya que es quien identifica al proceso en
    la tabla de procesos; el path es necesario si todavía no fue creado el proceso y hay que ubicar al programa
    en el disco; y el state debe ser necesariamente ready para poder poner a correr un proceso.
    ```

- __2:__ Entender las clases __IoDeviceController__, __PrinterIODevice__ y poder explicar como funcionan

    ```
    En el caso de la clase IoDeviceController podemos ver que simula e implementa de manera
    funcional los drivers para controlar las interrupciones de tipo I/O, dentro de su clase posee 
    funciones para inicializar y manipular los estados de dichas interrupciones permitiendo el 
    correcto funcionamiento segun sea necesario mientras que la clase __PrinterIODevice__ vendria a 
    ser una clase que permite el encapsulamiento y la manifestacion de dichas interrupciones ya que 
    recibe como parametro la clase AbstractIODevice que permite abstraernos y simular una 
    interrupcion, permitiendo asi que la clase PrinterIODevice procese, interprete e imprima las 
    interrupciones.
    ```

- __3:__ Explicar cómo se llegan a ejecutar __IoInInterruptionHandler.execute()__ y  __IoOutInterruptionHandler.execute()__

    ```
    IoInInterruptionHandler.execute() se llega a ejecutar cuando el CPU lee una instrucción de tipo ASM.IO().
    Esto crea una interrupción request (IRQ) de tipo #IO_IN y se llama al Interrupt Vector para que maneje dicha 
    interrupción. Una vez que el Interrupt Vector agarra dicha IRQ, ejecuta el IoInInterruptionHandler pasándola
    como argumento, es decir, se llama a la función __IoInInterruptionHandler.execute()__.
    Por otro lado, IoOutInterruptionHandler.execute() se ejecuta cuando terminó de ejecutarse la operación I/O
    por la que estaba esperando el proceso en el IODevice. Este último es quien se encarga de lanzar la interrupción
    #IO_OUT al Interrupt Vector para que, por el mismo proceso antes descrito, llegue a ejecutar el handler IoOut.
    ```

- __4:__    Hagamos un pequeño ejercicio (sin codificarlo):

- __4.1:__ Que esta haciendo el CPU mientras se ejecuta una operación de I/O??

    ```
    Al Ejecutar una interrupcion de tipo I/O la CPU lo que hara es ejecutar otro programa
    en el caso de que haya más programas en la cola en estado de Ready para ejecutarse o en
    el caso de que no haya ningun otro programa para ejecutar, el programa que ejecuto la 
    interrupcion de tipo I/O deberia haber cambiado su estado a Waiting para esperar la 
    respuesta externa a la maquina por lo que una vez recibida dicha respuesta lo que pasara
    sera que volvera a cambiar el estado para posteriormente continuar la ejecucion del
    programa
    ```

- __4.2:__ Si la ejecucion de una operacion de I/O (en un device) tarda 3 "ticks", cuantos ticks necesitamos para ejecutar el siguiente batch?? Cómo podemos mejorarlo??
    (tener en cuenta que en el emulador consumimos 1 tick para mandar a ejecutar la operacion a I/O)

    ```python
    prg1 = Program("prg1.exe", [ASM.CPU(2), ASM.IO(), ASM.CPU(3), ASM.IO(), ASM.CPU(2)])
    prg2 = Program("prg2.exe", [ASM.CPU(4), ASM.IO(), ASM.CPU(1)])
    prg3 = Program("prg3.exe", [ASM.CPU(3)])
    ```

    ```
    Sin utilizar multiprogramación, si cada operación de entrada/salida tarda 3 ticks + 1 por mandar la instrucción,
    el batch compuesto por prg1, prg2 y prg3 tardaría:
    prg1: 2+(1+3)+3+(1+3)+2 = 15
     +
    prg2: 4+(1+3)+1 = 9
     +
    prg3: 3
     =
    27 ticks

    Si utilizamos multiprogramación, los procesos no tendrían que esperar las operaciones de I/O de los otros.
    Por lo tanto, sería:
    tick 01: prg1 cpu
    tick 02: prg1 cpu
    tick 03: prg1 io
    tick 04: prg2 cpu, prg1 waiting io
    tick 05: prg2 cpu, prg1 waiting io
    tick 06: prg2 cpu, prg1 waiting io
    tick 07: prg2 cpu
    tick 08: prg2 io
    tick 09: prg3 cpu, prg2 waiting io
    tick 10: prg3 cpu, prg2 waiting io
    tick 11: prg3 cpu, prg2 waiting io
    tick 12: prg3 kill
    tick 13: prg1 cpu
    tick 14: prg1 cpu
    tick 15: prg1 cpu
    tick 16: prg1 io
    tick 17: prg2 cpu, prg1 waiting io
    tick 18: prg2 kill, prg1 waiting io
    tick 19: prg1 waiting io
    tick 20: prg1 cpu
    tick 21: prg1 cpu
    tick 22: prg1 kill

    Nos ahorramos 5 ticks.
    ```

- __5:__ Hay que tener en cuenta que los procesos se van a intentar ejecutar todos juntos ("concurrencia"), pero como solo tenemos un solo CPU, vamos a tener que administrar su uso de forma óptima.
      Como el S.O. es una "maquina de estados", donde las cosas "pasan" cada vez que se levanta una interrupcion (IRQ) vamos a tener que programar las 4 interrupciones que conocemos:  
    
    - Cuando se crea un proceso (__#NEW__) se debe intentar hacerlo correr en la CPU, pero si la CPU ya esta ocupada, debemos mantenerlo en la cola de Ready.
    - Cuando un proceso entre en I/O (__#IO_IN__), debemos cambiar el proceso corriendo en CPU (__"running"__) por otro, para optimizar el uso de __CPU__
    - Cuando un proceso sale en I/O (__#IO_OUT__), se debe intentar hacerlo correr en la CPU, pero si la CPU ya esta ocupada, debemos mantenerlo en la cola de Ready.
    - Cuando un proceso termina (__#KILL__), debemos cambiar el proceso corriendo en CPU (__"running"__) por otro, para optimizar el uso de __CPU__

.

- __6:__ Ahora si, a programar... tenemos que "evolucionar" nuestro S.O. para que soporte __multiprogramación__  

- __6.1:__ Implementar la interrupción #NEW
    ```python
    # Kernel.run() debe lanzar una interrupcion de #New para que se resuelva luego por el S.O. 
    ###################

    ## emulates a "system call" for programs execution
    def run(self, program):
        newIRQ = IRQ(NEW_INTERRUPTION_TYPE, program)
        HARDWARE.interruptVector.handle(newIRQ)
    ```

- __6.2:__ Implementar los compoenentes del S.O.: 
    - Loader
    - Dispatcher
    - PCB
    - PCB Table
    - Ready Queue
    - Las 4 interrupciones: 
        - __#NEW__ 
        - __#IO_IN__
        - __#IO_OUT__
        - __#KILL__



- __6.3:__        Implementar una version con __multiprogramación__ (donde todos los procesos se encuentran en memoria a la vez)


    ```python
    # Ahora vamos a intentar ejecutar 3 programas a la vez
    ###################
    prg1 = Program("prg1.exe", [ASM.CPU(2), ASM.IO(), ASM.CPU(3), ASM.IO(), ASM.CPU(2)])
    prg2 = Program("prg2.exe", [ASM.CPU(4), ASM.IO(), ASM.CPU(1)])
    prg3 = Program("prg3.exe", [ASM.CPU(3)])

    # executamos los programas "concurrentemente"
    kernel.run(prg1)
    kernel.run(prg2)
    kernel.run(prg3)

    ## start
    HARDWARE.switchOn()

    ```
