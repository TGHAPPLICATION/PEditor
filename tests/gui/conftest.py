import pytest

from peditor.core.service import DocumentService
from peditor.ui.app import MainWindow


@pytest.fixture
def make_window(qtbot):
    services = []

    def make(service=None, **kwargs):
        service = service or DocumentService()
        services.append(service)
        window = MainWindow(service, **kwargs)
        qtbot.addWidget(window)
        window.show()
        return window

    yield make
    for service in services:
        service.close()
