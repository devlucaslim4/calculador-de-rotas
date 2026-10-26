import pandas as pd

from analysis_engine import prepare_analysis
from dashboard import (
    _animated_route_figure,
    _map_route_label,
    _map_view_state,
    _sample_map_path,
)
from route_processor import RouteGeometry


def test_route_label_includes_id_user_and_unit():
    dataframe = pd.DataFrame(
        {
            "ID RESPOSTA": [101],
            "NOME": ["Ana"],
            "UNIDADE": ["SP"],
        }
    )
    analysis = prepare_analysis(dataframe)

    label = _map_route_label(analysis.data.iloc[0], analysis)

    assert label == "101 • Ana • SP"


def test_3d_camera_centers_and_inclines_the_route():
    path = [
        [-46.6333, -23.5505],
        [-46.6400, -23.5550],
        [-46.6565, -23.5614],
    ]

    view_state = _map_view_state(path)

    assert view_state.pitch == 55
    assert view_state.zoom > 10
    assert -46.6565 <= view_state.longitude <= -46.6333
    assert -23.5614 <= view_state.latitude <= -23.5505


def test_animation_samples_long_path_and_keeps_endpoints():
    path = [[-46.7 + index * 0.001, -23.6 + index * 0.0005] for index in range(200)]

    sampled = _sample_map_path(path, max_points=40)

    assert len(sampled) == 40
    assert sampled[0] == path[0]
    assert sampled[-1] == path[-1]


def test_animated_map_contains_car_and_playback_frames():
    path = [
        [-46.6333, -23.5505],
        [-46.6400, -23.5550],
        [-46.6565, -23.5614],
    ]
    geometry = RouteGeometry(
        path=tuple(tuple(point) for point in path),
        distance_km=3.62,
        duration_minutes=10.2,
    )

    figure = _animated_route_figure(path, "101 • Ana • SP", geometry, light_mode=False)

    assert len(figure.frames) == 3
    assert figure.data[3].text == ("CARRO",)
    assert figure.data[3].marker.color == "#E8BE69"
    assert figure.frames[-1].data[1].lon == (path[-1][0],)
    assert figure.frames[-1].traces == (1, 3)
    assert len(figure.layout.updatemenus[0].buttons) == 3
    assert "Iniciar viagem" in figure.layout.updatemenus[0].buttons[0].label

