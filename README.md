# modlog-modern

Минимальная замена **видимого вывода** штатного ModLog в Red-DiscordBot 3.5.x.

Cog не переписывает хранение case'ов и не подменяет `redbot.core.modlog`. Red продолжает создавать, нумеровать, хранить и редактировать штатные ModLog case'ы. `modlog-modern` слушает `modlog_case_create` / `modlog_case_edit` и отправляет их в свой канал.

## Что изменено

Для всех case'ов, кроме `warning`, используется штатный `Case.message_content()` Red без изменений.

Для `warning` используется тот же штатный renderer, после чего выполняется только две правки:

1. Из Reason убирается служебная подсказка с готовой командой `unwarn`.
2. ID предупреждения из этой команды выводится отдельным полем **«ID предупреждения»**.

То есть формат Ban/Kick/Mute/Unban и остальных case'ов остаётся ровно таким, каким его формирует установленная версия Red.

## Почему не надо копировать весь `redbot/core/modlog.py`

`Warnings` и другие cog'и вызывают именно штатный `redbot.core.modlog.create_case()`. Если заменить сам движок ModLog отдельной несовместимой реализацией, придётся поддерживать его API, Config, нумерацию case'ов, события и миграции Red.

Здесь штатный движок остаётся активным, а отключается только его отправка сообщений в канал. Это позволяет использовать `modlog-modern` как единственный видимый ModLog без дублирования внутренней логики Red.

## Установка

```text
[p]repo add modlog-modern https://github.com/neuropolimer/modlog-modern
[p]cog install modlog-modern modlogmodern
[p]load modlogmodern
```

## Переключить сервер на ModLogModern

```text
[p]modlogmodern takeover #канал-логов
```

`takeover` делает сразу три вещи:

- включает `modlog-modern` в указанном канале;
- очищает штатный ModLog channel через `redbot.core.modlog.set_modlog_channel(..., None)`, поэтому стандартный case больше не отправляется вторым сообщением;
- отключает `Warnings.toggle_channel`, поэтому пропадает отдельное сообщение вида «@user был предупреждён».

При этом штатная база ModLog case'ов продолжает работать.

## Команды

```text
[p]modlogmodern status
[p]modlogmodern channel #канал
[p]modlogmodern takeover #канал
[p]modlogmodern on
[p]modlogmodern off
[p]modlogmodern release #канал
```

`release` отключает ModLogModern и возвращает штатный вывод Red ModLog в указанный канал.

## Warning ID

В стандартном `Warnings` ID предупреждения — это ID сообщения с командой `warn` (`ctx.message.id`). Warnings хранит запись под этим ID и вставляет его последним аргументом в подсказку `unwarn`.

ModLogModern извлекает этот ID независимо от языка локализации: он не ищет английское слово `Use`, а разбирает числовые аргументы inline-команды в конце стандартного warning reason.
