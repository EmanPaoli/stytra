from multiprocessing import Process, Event, Queue
import vispy
from vispy import scene, app
from time import process_time_ns
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton
import time
import datetime
from stytra.stimulation import ProtocolRunner
from stytra.collectors.accumulators import DynamicLog, FramerateAccumulator
from stytra.utilities import FramerateRecorder
from stytra.stimulation.stimuli import Pause, DynamicStimulus


class Circle:
    def __init__(self, scene):
        self.scene = scene
        self.circle = None
        self.name = 'circle'
        self.circle = vispy.scene.visuals.Ellipse(
            center=(100, 100),
            color="white",
            parent=self.scene,
            radius=(10, 10),
            name=self.name
            )
        self.circle.visible = False

    def paint(self):
        self.circle.visible = True
        self.circle.update()

    def clear(self):
        self.circle.visible = False
        self.circle.update()


class Background:
    def __init__(self, scene=None, color=(0, 0, 0), w=None, h=None):
        self.scene = scene
        self.circle = None
        self.color = color
        self.w = w
        self.h = h
        self.background = vispy.scene.visuals.Rectangle(
            center=(self.w, self.h),
            color="black",
            parent=self.scene,
            height=self.h,
            width=self.w
        )
        self.background.visible = False

    def paint(self):
        self.background.update()



class Pause:
    def __init__(self, scene):
        self.scene = scene

    def paint(self):
        self.scene.SceneCanvas(size=(800, 600), show=True)


class StimulusDisplay(Process):
    def __init__(self, sync_events=None, experiment=None):
        super().__init__()

        self.experiment = experiment
        self.protocol = experiment.protocol
    # internal communication
        self.sig_protocol_started = False
        self.sig_protocol_updated = False
        self.sig_ongoing_protocol = False
        self.stimulus_accumulator = None
        self.t0 = None
    # communication between processes
        self.start_event = sync_events['start_event']
        self.abort_event = sync_events['abort_event']
        self.stop_event = sync_events['stop_event']

        self.el = None
        self.txt = None
        self.prev_time = None
        self.stim = None
        self.canvas = None
        self.scene = None
        self.scen = None
        self.w = 800
        self.h = 600

        self.t_end = None
        self.completed = False
        self.t = 0
        self.past_stimulus_elapsed = None

        self.stimuli = []
        self.i_current_stimulus = 0  # index of current stimulus
        self.current_stimulus = None  # current stimulus object

        self.past_stimuli_elapsed = None  # time elapsed in previous stimuli
        self.dynamic_log = None  # dynamic log for stimuli

        self.framerate_rec = FramerateRecorder()  # ???
        self.framerate_acc = FramerateAccumulator(experiment=self.experiment) # ???

        vispy.use("PyQt5")
        self.canvas = scene.SceneCanvas(title='Stytra stimulus display',
                                        size=(self.w, self.h),
                                        show=True
                                        )
        view = self.canvas.central_widget.add_view()
        self.scene = view.scene
        self.txt = scene.visuals.Text(parent=view.scene, color="white", pos=(40, 40))
        self.timer = vispy.app.Timer("auto", connect=self.update, start=True)
        vispy.app.run()

    def run(self):
        while True:
            if self.start_event.is_set() and not self.sig_ongoing_protocol:
                self.update_protocol()
                self.sig_protocol_started = True
                self.sig_ongoing_protocol = True
                self.t0 = process_time_ns()
                self.current_stimulus.start()

    def update(self, *args):
        if self.sig_protocol_started and self.sig_ongoing_protocol:
            if not self.abort_event.is_set():
                ctime = process_time_ns()
                dif = ctime - self.t0
                self.stimulus_accumulator += dif
                if self.stimulus_accumulator > self.current_stimulus.duration:
                    self.current_stimulus.stop()
                    if self.i_current_stimulus >= len(self.stimuli) - 1:
                        self.stop_event.set()
                    else:
                        self.i_current_stimulus += 1
                        self.current_stimulus = self.stimuli[self.i_current_stimulus]
                        self.t0 = process_time_ns()
                        self.current_stimulus.start()
                self.current_stimulus.update()  # use stimulus update function
                if isinstance(self.current_stimulus, DynamicStimulus):
                    self.sig_stim_change.emit(self.i_current_stimulus)
                    self.update_dynamic_log()  # update dynamic log for stimulus

                self.framerate_rec.update_framerate()
                if self.framerate_rec.i_fps == self.framerate_rec.n_fps_frames - 1:
                    self.framerate_acc.update_list(self.framerate_rec.current_framerate)
            else:
                self.reset()

    def reset(self):
        self.current_stimulus.clear()
        self.protocol.start.clear()
        self.abort_event.clear()

    def stop(self):
        pass

    def update_protocol(self):
        self.stimuli = self.protocol._get_stimulus_list()
        self.i_current_stimulus = 0
        self.current_stimulus = self.stimuli[self.i_current_stimulus]
        # pass experiment to stimuli for calibrator and asset folders:
        # for stimulus in self.stimuli:
        #     stimulus.initialise_external(self.experiment)
        #
        # if self.dynamic_log is None:
        #     self.dynamic_log = DynamicLog(self.stimuli, experiment=self.experiment)
        # else:
        #     self.dynamic_log.update_stimuli(self.stimuli)  # new stimulus log

        self.sig_protocol_updated = True


class Asker(Process):
    def __init__(self, event):
        super().__init__()
        self.start_event = event

    def run(self):
        time.sleep(3)
        self.start_event.set()


if __name__ == '__main__':
    start_event = Event()
    stimulus_process = StimulusDisplay(start_event)
    asker = Asker(start_event)
    asker.start()
    stimulus_process.start()








