from usr.libs import Application
from usr.components import (
    led_manager,
    net_manager,
    power_manager,
    audio_manager,
    qth_client,
    ai_manager,
)
from usr.configure import settings


def create_application(name="ChatGPT", version=settings.get_version()):
    app = Application(name, version=version)

    # app.register("power_manager", power_manager)
    # app.register("led_manager", led_manager)
    app.register("net_manager", net_manager)
    # app.register("audio_manager", audio_manager)
    app.register("qth_client", qth_client)
    # app.register("ai_manager", ai_manager)

    return app


if __name__ == "__main__":
    app = create_application()
    app.run()
