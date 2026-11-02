#include <QBuffer>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>
#include <QUrlQuery>
#include <QVariantList>

#ifdef HAVE_LAYERSHELL
#include <LayerShellQt/Shell>
#include <LayerShellQt/Window>
#endif

namespace {
const char *kBase = "http://127.0.0.1:8756";

QString readToken()
{
    QFile file(QDir::homePath() + "/.config/silisten/token");
    if (!file.open(QIODevice::ReadOnly))
        return {};
    return QString::fromUtf8(file.readAll()).trimmed();
}
} // namespace

class Backend : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString status READ status NOTIFY changed)
    Q_PROPERTY(QString title READ title NOTIFY changed)
    Q_PROPERTY(QString subtitle READ subtitle NOTIFY changed)
    Q_PROPERTY(QString text READ text NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
    Q_PROPERTY(QString timerText READ timerText NOTIFY changed)
    Q_PROPERTY(QVariantList levels READ levels NOTIFY changed)
    Q_PROPERTY(QVariantList sources READ sources NOTIFY changed)
    Q_PROPERTY(QVariantList languages READ languages NOTIFY changed)
    Q_PROPERTY(QString language READ language NOTIFY changed)
    Q_PROPERTY(QString inputDevice READ inputDevice NOTIFY changed)
    Q_PROPERTY(int reveal READ reveal NOTIFY changed)
    Q_PROPERTY(int hideRequest READ hideRequest NOTIFY changed)
    Q_PROPERTY(bool visible READ visible WRITE setVisible)

public:
    explicit Backend(QObject *parent = nullptr) : QObject(parent)
    {
        m_token = readToken();
        m_timer.setInterval(16);
        connect(&m_timer, &QTimer::timeout, this, &Backend::poll);
        m_timer.start();
        QTimer::singleShot(0, this, [this] {
            fetchList("/sources", m_sources);
            fetchList("/languages", m_languages);
        });
    }

    QString status() const { return m_status; }
    QString text() const { return m_text; }
    QString error() const { return m_error; }
    QVariantList levels() const { return m_levels; }
    QVariantList sources() const { return m_sources; }
    QVariantList languages() const { return m_languages; }
    QString language() const { return m_language; }
    QString inputDevice() const { return m_inputDevice; }
    int reveal() const { return m_reveal; }
    int hideRequest() const { return m_hide; }

    void setVisible(bool value)
    {
        if (m_visible == value)
            return;
        m_visible = value;
        if (!value)
            m_levels.clear();
        emit changed();
    }
    bool visible() const { return m_visible; }

    QString title() const
    {
        if (m_status == "listening") return QStringLiteral("Listening");
        if (m_status == "thinking") return QStringLiteral("Transcribing");
        if (m_status == "error") return QStringLiteral("Something went wrong");
        if (m_status == "done") return QStringLiteral("Transcription");
        return QStringLiteral("Silisten");
    }

    QString subtitle() const
    {
        if (m_status != "thinking") return {};
        if (m_phase == "identifying speakers") return QStringLiteral("Working out who is speaking");
        if (m_phase == "decoding") return QStringLiteral("Opening the file");
        return QStringLiteral("Turning your voice into text");
    }

    QString timerText() const
    {
        int total = int(m_duration);
        return QStringLiteral("%1:%2").arg(total / 60).arg(total % 60, 2, 10, QLatin1Char('0'));
    }

    Q_INVOKABLE void startRecording(bool append)
    {
        QJsonObject body{{"append", append}};
        post("/record/start", body);
    }
    Q_INVOKABLE void stopRecording() { post("/record/stop", {}); }
    Q_INVOKABLE void upload(const QUrl &url)
    {
        QJsonObject body{{"path", url.toLocalFile()}, {"append", !m_text.isEmpty()}};
        post("/upload", body);
    }
    Q_INVOKABLE void setLanguage(const QString &code)
    {
        post("/config", QJsonObject{{"language", code}});
    }
    Q_INVOKABLE void setInputDevice(const QString &id)
    {
        post("/config", QJsonObject{{"input_device", id}});
    }

signals:
    void changed();

private:
    void poll()
    {
        if (m_inFlight)
            return;
        m_inFlight = true;
        QUrl url(QStringLiteral("%1/state?levels=1&visible=%2").arg(kBase).arg(m_visible ? 1 : 0));
        QNetworkRequest request(url);
        request.setRawHeader("X-Silisten-Token", m_token.toUtf8());
        auto *reply = m_nam.get(request);
        connect(reply, &QNetworkReply::finished, this, [this, reply] {
            m_inFlight = false;
            const QByteArray payload = reply->readAll();
            reply->deleteLater();
            apply(payload);
        });
    }

    void fetchList(const QString &path, QVariantList &target)
    {
        QNetworkRequest request(QUrl(QString::fromLatin1(kBase) + path));
        request.setRawHeader("X-Silisten-Token", m_token.toUtf8());
        auto *reply = m_nam.get(request);
        connect(reply, &QNetworkReply::finished, this, [this, reply, &target] {
            const QByteArray payload = reply->readAll();
            reply->deleteLater();
            QJsonDocument doc = QJsonDocument::fromJson(payload);
            target = doc.array().toVariantList();
            emit changed();
        });
    }

    void post(const QString &path, const QJsonObject &body)
    {
        QNetworkRequest request(QUrl(QString::fromLatin1(kBase) + path));
        request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
        request.setRawHeader("X-Silisten-Token", m_token.toUtf8());
        auto *reply = m_nam.post(request, QJsonDocument(body).toJson(QJsonDocument::Compact));
        connect(reply, &QNetworkReply::finished, reply, &QNetworkReply::deleteLater);
    }

    void apply(const QByteArray &payload)
    {
        QJsonParseError error{};
        const QJsonDocument doc = QJsonDocument::fromJson(payload, &error);
        if (error.error != QJsonParseError::NoError || !doc.isObject())
            return;
        const QJsonObject object = doc.object();

        m_status = object.value("status").toString(QStringLiteral("idle"));
        m_text = object.value("text").toString();
        m_error = object.value("error").toString();
        m_phase = object.value("phase").toString();
        m_duration = object.value("duration").toDouble();
        m_reveal = object.value("reveal").toInt();
        m_hide = object.value("hide_request").toInt();

        const QJsonObject config = object.value("config").toObject();
        m_language = config.value("language").toString();
        m_inputDevice = config.value("input_device").toString(QStringLiteral("default"));

        if (m_status == "listening") {
            for (const QJsonValue &value : object.value("levels").toArray())
                m_levels.append(value.toDouble());
            if (m_levels.size() > 4000)
                m_levels = m_levels.mid(m_levels.size() - 4000);
        } else if (!m_levels.isEmpty()) {
            m_levels.clear();
        }

        emit changed();
    }

    QNetworkAccessManager m_nam;
    QTimer m_timer;
    QString m_token;
    QString m_status = QStringLiteral("idle");
    QString m_text;
    QString m_error;
    QString m_phase;
    QString m_language;
    QString m_inputDevice = QStringLiteral("default");
    double m_duration = 0;
    int m_reveal = 0;
    int m_hide = 0;
    bool m_visible = false;
    bool m_inFlight = false;
    QVariantList m_levels;
    QVariantList m_sources;
    QVariantList m_languages;
};

int main(int argc, char *argv[])
{
    bool layerShell = false;
    const QString desktop = qEnvironmentVariable("XDG_CURRENT_DESKTOP").toLower();
    const bool wayland = !qEnvironmentVariableIsEmpty(qgetenv("WAYLAND_DISPLAY"));
    const bool desktopSupportsLayerShell = !desktop.contains("gnome") && !desktop.contains("unity")
                                           && !desktop.contains("pantheon");
    if (wayland && desktopSupportsLayerShell) {
#ifdef HAVE_LAYERSHELL
        LayerShellQt::Shell::useLayerShell();
        layerShell = true;
#endif
    }
    if (!layerShell)
        qputenv("QT_QPA_PLATFORM", "xcb");

    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("silisten"));

    Backend backend;

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("backend", &backend);
    engine.load(QUrl::fromLocalFile(QCoreApplication::applicationDirPath() + "/qml/main.qml"));
    if (engine.rootObjects().isEmpty())
        return 1;

    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
    if (!window)
        return 1;

    if (layerShell) {
#ifdef HAVE_LAYERSHELL
        if (auto *shell = LayerShellQt::Window::get(window)) {
            shell->setLayer(LayerShellQt::Window::LayerTop);
            shell->setAnchors({LayerShellQt::Window::AnchorBottom, LayerShellQt::Window::AnchorLeft,
                               LayerShellQt::Window::AnchorRight});
            shell->setExclusiveZone(0);
            shell->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityOnDemand);
        }
#endif
    }

    auto place = [window] {
        if (!QGuiApplication::platformName().startsWith(QLatin1String("xcb")))
            return;
        QScreen *screen = window->screen();
        if (!screen)
            return;
        const QRect area = screen->geometry();
        window->setPosition(area.x() + (area.width() - window->width()) / 2,
                            area.y() + area.height() - window->height());
    };
    QObject::connect(window, &QWindow::heightChanged, window, place);
    QObject::connect(window, &QWindow::widthChanged, window, place);
    QObject::connect(window, &QWindow::visibleChanged, window, place);
    place();

    return app.exec();
}

#include "main.moc"
