# rtos.py file
from machine import Timer
from time import sleep_ms
import micropython

class rtos_task:
    """ rtos task class used to implement tasks """

    STATE_INIT = 0
    STATE_PENDING = 1
    STATE_READY = 2
    STATE_RUNNING = 3
    STATE_COMPLETE = 4

    def __init__ (self, priority, param1=None):
        self.priority = priority
        self.param1 = param1
        self.rtos_container = None
        self.task_state = self.STATE_INIT

    def switch_to_ready (self):
        if self.task_state == self.STATE_PENDING:
            self.task_state = self.STATE_READY

    def get_task_state (self):
        return self.task_state

    # called when task shoudl be initialized
    # will call task_init
    def init (self):
        self.task_init(self.param1)
        # create generator for task_body
        self.task_generator = self.task_body(self.param1)
        self.task_state = self.STATE_PENDING

    # called when the task should be executed.
    # will call task_body
    def execute_task (self):
        if self.task_state == self.STATE_READY:
            self.task_state = self.STATE_RUNNING
            try:
                next(self.task_generator)
            except Exception as StopIteration:
                self.task_state = self.STATE_COMPLETE
            else:
                self.task_state = self.STATE_PENDING

    # Task implementation
    # task definition should override 
    # task_init and task_body
    def task_init(self, param1):
        """Task Init function.

        It is expected that a derived rtos_task class will implement this
        function.
        """
        raise NotImplementedError

    def task_body(self, param1):
        """Task Body function.

        It is expected that a derived rtos_task class will implement this
        function.
        """
        raise NotImplementedError

class background_task(rtos_task):
    """ default implementation of the background task """
    def __init__ (self):
        rtos_task.__init__(self,priority=0)

    def task_init(self,param1):
        pass

    def task_body(self,param1):
        sleep_ms(1)
        pass

class rtos:
    """rtos scheduler class """
    def __init__ (self, s_table=[], t_list=[], verbose=0):
        self.exit_request = 0
        self.schedule_table_index = 0
        self.schedule_table = s_table
        self.task_list = {}
        self.current_task_id = 0
        self.verbose = verbose
        # initialize in list order
        for t in t_list:
            self.add_task (t)
        # then initialize background task
        # add background task
        self.add_task (background_task())

    def __get_high_task_prio_from_state (self):
        # get list of ready task
        ready_list_index = [t for t in self.task_list if self.task_list[t].get_task_state()==rtos_task.STATE_READY]
        # get highest priority
        if ready_list_index == []:
            return 0
        else:
            return max(ready_list_index)

    def schedule_task(self, unused):
        # find highest priority
        index=self.__get_high_task_prio_from_state()
        while index != 0:
            if index in self.task_list:
                self.current_task_id = index
                # execute task
                self.task_list[index].execute_task()
            # get next ready
            index=self.__get_high_task_prio_from_state()
        self.current_task_id = 0

    def scheduler_tick_call(self):
        if len(self.schedule_table) != 0:
            # get list for current tick
            _current_entry = self.schedule_table[self.schedule_table_index]
            # switch each entry to ready state
            for i in _current_entry:
                if i in self.task_list:
                    self.task_list[i].switch_to_ready()              
            # increment schedule_table_index for next time
            self.schedule_table_index = self.schedule_table_index + 1
            if self.schedule_table_index>=len(self.schedule_table):
                self.schedule_table_index = 0
            # schedule tasks
            micropython.schedule(self.schedule_task,None)
        
    def add_task ( self, task):
        id = task.priority
        if id in self.task_list:
            print('Error: task id: ',id,' already exist')
        else:
            if self.verbose>0: print ('Add task ', id)
            self.task_list[id]=task
            # update link to calling rtos
            task.rtos_container = self
            # run init 
            self.task_list[id].init()

    def activate_task (self, id):
        if id not in self.task_list:
            print('Error: no task with id: ', id)
        else:
            if self.verbose>1: print ('Activate task ', id)
            self.task_list[id].switch_to_ready()
            micropython.schedule(self.schedule_task,None)

    def remove_task (self, id):
        if not id in self.task_list:
            print('Error: task id: ',id,' does not exist')
        else:
            if self.verbose>0: print('Remove task ', id)
            self.task_list[id].rtos_container = None
            del self.task_list[id]

    def start(self):
        # run background task
        while not self.exit_request:
            self.task_list[0].task_body(param1=None)

    def stop(self):
        self.exit_request=1
