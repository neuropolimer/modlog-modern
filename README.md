# modlog-modern

Небольшой cog для Red-DiscordBot 3.5.x, который меняет только видимый вывод ModLog.

Штатный `redbot.core.modlog` остаётся на месте: case'ы по-прежнему создаёт, хранит и нумерует сам Red. Cog слушает события ModLog и отправляет сообщения в выбранный канал.

Для обычных case'ов используется стандартный вывод Red. У `warning` убирается служебная подсказка с командой `unwarn`, а ID предупреждения выводится отдельно.

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

`takeover` включает ModLogModern, отключает стандартную отправку ModLog в канал и отдельные сообщения Warnings. Сама база case'ов Red при этом не меняется.

## Команды

```text
[p]modlogmodern status
[p]modlogmodern channel #канал
[p]modlogmodern takeover #канал
[p]modlogmodern on
[p]modlogmodern off
[p]modlogmodern release #канал
```

`release` отключает cog и возвращает штатный вывод Red ModLog.

## Warning ID

Warnings хранит предупреждение под ID сообщения с командой `warn`. ModLogModern достаёт этот ID из стандартного reason и показывает отдельным полем, не завязываясь на язык интерфейса Red.
