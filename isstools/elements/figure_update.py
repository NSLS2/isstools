from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.widgets import Cursor



def update_figure(axes, toolbar, canvas):
    start = 0
    step = -0.05
    for ax in axes:
        ax.clear()
        # cursor = Cursor(ax, useblit=True, color='green', linewidth=0.75)
    for i, ax in enumerate(axes):
        offset = start + i * step
        ax.spines['left'].set_position(('axes', offset))
        ax.spines['right'].set_visible(False)
        ax.yaxis.set_label_position("left")
        ax.yaxis.tick_left()
        ax.tick_params(axis='y', rotation=90)
    axes[-1].spines['right'].set_visible(True)


    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)


def update_figure_with_colorbar(axes, toolbar, canvas,figure):
    if len(figure.axes) >1:
        figure.axes[-1].remove()
    for ax in axes:
        ax.clear()
        # cursor = Cursor(ax, useblit=True, color='green', linewidth=0.75)

    toolbar.update()
    canvas.draw_idle()
    axes[-1].grid(alpha=0.4)


def setup_figure(parent, layout):
    figure = Figure()
    figure.set_facecolor(color='#FcF9F6')
    canvas = FigureCanvas(figure)
    figure.ax = figure.add_subplot(111)
    toolbar = NavigationToolbar(canvas, parent, coordinates=True)
    layout.addWidget(toolbar)
    layout.addWidget(canvas)
    canvas.draw_idle()
    canvas._cursor = Cursor(figure.ax, useblit=True, color='green', linewidth=0.75)
    figure.ax.grid(alpha=0.4)
    #figure.tight_layout()

    return figure, canvas,toolbar



