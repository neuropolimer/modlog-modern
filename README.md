# modlog-modern

Cog для Red-DiscordBot 3.5.x, который меняет видимый вывод ModLog, не заменяя штатную базу case'ов Red.

Для обычных case'ов используется стандартный renderer Red. У `warning` служебная подсказка с готовой командой `unwarn` убирается, а ID предупреждения показывается отдельно.

Очистка применяется не только к новым сообщениям в лог-канале, но и к повторному просмотру истории через `case`, `casesfor` и `listcases`. Сами сохранённые case'ы при этом не переписываются.

## Установка

```text
[p]repo add modlog-modern https://github.com/neuropolimer/modlog-modern
[p]cog install modlog-modern modlogmodern
[p]load modlogmodern
```

Переключить сервер на новый вывод:

```text
[p]modlogmodern takeover #канал-логов
```

`takeover`:
- включает ModLogModern;
- отключает стандартную отправку Red ModLog;
- отключает отдельное сообщение Warnings;
- сохраняет состояние, необходимое для последующего `release`.

`off` не даст отключить ModLogModern, пока takeover активен, чтобы сервер случайно не остался вообще без видимых логов.

## Команды

```text
[p]modlogmodern status
[p]modlogmodern channel #канал
[p]modlogmodern takeover #канал
[p]modlogmodern on
[p]modlogmodern off
[p]modlogmodern release
[p]modlogmodern release #канал
```

`release` возвращает штатный Red ModLog. Для новых takeover-состояний также восстанавливается сохранённая настройка отдельного Warnings-уведомления. Старые takeover-состояния до версии 0.3 распознаются автоматически и мигрируются безопасно.

## Warning ID

Warnings хранит предупреждение под ID исходного сообщения команды `warn`. ModLogModern достаёт этот ID из стандартного reason и показывает отдельным полем, не завязываясь на язык интерфейса Red.

## Обновление

```text
[p]repo update
[p]cog update modlogmodern
[p]reload modlogmodern
```
