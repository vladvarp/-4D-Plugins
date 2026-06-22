---
title: VAr Tools
tagline: Набор утилит для Cinema 4D, созданных для ускорения повседневной работы. Все плагины находятся в меню VAr Tools.
version: v2.36
author: V.Ar Production
updated: Июнь 2026
icon: ico/Var_tools/varp_tools.png
tags: [Моделирование, Процедурный, Анимация, Автоматизация]
license: GPL v3
cinema4d: R26+
os: Windows
renderer: Все рендереры
download: https://github.com/vladvarp/-4D-Plugins/releases/download/C4D/4DPluginInstaller.exe
github: https://github.com/vladvarp/-4D-Plugins
---

## О наборе

VAr Tools — набор практичных утилит для Cinema 4D, заточенных под реальный рабочий процесс. Вместо того чтобы делать одно большое всё-в-одном, каждый инструмент решает конкретную задачу: сбросить ось на пол, почистить сцену от мусорных нуллов, сгенерировать нестандартную геометрию и др.
Особенно полезен на стадии подготовки сцены и финального клинапа — рутинные операции, которые обычно съедают по несколько минут, делаются в один клик.

## Установка
::::steps
### Скачай программу
[[button:4DPluginInstaller.exe|https://github.com/vladvarp/-4D-Plugins/releases/download/C4D/4DPluginInstaller.exe]]
### Выбрать папку плагинов Cinema 4D
### Установить нужный пакет плагинов
### Плагин появится в меню [[badge:Beta|VAr Tools]]
::::

## Плагины

### Animation
::::tabs
### Animation
| Значок | Плагин | Описание | Галерея |
| ------ | ------ | -------- | ------- |
| [[ico:'ico/Var_tools/Animation/shift_anim_to_zero.png']]  | **Shift Animation2Zero** | Cдвигает все ключевые кадры сцены так, чтобы анимация начиналась с нужного кадра. | [[mdb:'Интерфейс'-n'shift_anim_to_zero'-b8]] |
| [[ico:'ico/Var_tools/Animation/scale_anim_timeline.png']] | **Scale Animation Timeline** | Масштабирует анимацию и весь таймлайн сцены пропорционально относительно нуля, мгновенно растягивая или сжимая длительность по введённому новому количеству кадров. | [[mdb:'Интерфейс'-n'scale_anim_timeline'-b8]] |
::::

### Tools

::::tabs
### Axis


| Значок | Плагин | Описание |
| ------ | ------ | -------- |
| [[ico:'ico/Var_tools/Tools/Axis/Axis2Bottom.png']]  | **Axis2Bottom** | Смещает ось (pivot) выделенных объектов в нижнюю центральную точку их bounding box (по X/Z — центр, по Y — нижняя грань). |
| [[ico:'ico/Var_tools/Tools/Axis/Axis2Center.png']]  | **Axis2Center** | Смещает ось (pivot) выделенных объектов в геометрический центр их bounding box. |
| [[ico:'ico/Var_tools/Tools/Axis/Axis_Droppng.png']] | **Axis Drop** | Опускает ось (pivot) выделенных объектов на нижнюю грань их bounding box, сохраняя X и Z позицию нетронутыми. |



### Location

| Значок | Плагин | Описание |
| ------ | ------ | -------- |
| [[ico:'ico/Var_tools/Tools/Location/Drop2Floor.png']]     | **Drop2Floor** | Опускает выделенные объекты (и их иерархии) на уровень пола (Y = 0). |
| [[ico:'ico/Var_tools/Tools/Location/Drop2Floor_0.png']]   | **Drop2Floor 0(XZ)** | Опускает выделенные объекты на уровень пола и центрирует их по осям X и Z. |
| [[ico:'ico/Var_tools/Tools/Location/Center2Parent.png']]  | **Center2Parent XZ** | Центрировать по X и Z в позицию родителя (мировое пространство, Y не меняется)  |
| [[ico:'ico/Var_tools/Tools/Location/Center2World.png']]   | **Center2World XZ** | Центрировать выделенные объекты по X и Z в мировом пространстве (Y не меняется) |



### Clean

| Значок | Плагин | Описание |
| ------ | ------ | -------- |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_Nulls.png']]          | **Clean Nulls** | Удаляет все Null-объекты без тегов из сцены. Дочерние объекты перемещаются на место Null-а, сохраняя мировые координаты. |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_EmptyNulls.png']]     | **Clean Empty Nulls** | Удаляет пустые Null-объекты без тегов и без дочерних объектов. Работает в несколько проходов для вложенных цепочек. |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_Objects.png']]        | **Clean Objects** | Удаляет все объекты того же типа, что и выделенный объект, сохраняя дочерние объекты. |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_EmptyObjects.png']]   | **Clean Empty Objects** | Удаляет все объекты того же типа, что и выделенный объект, НО только если у них нет дочерних объектов. |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_allTags.png']]        | **Clean All Tags** | Удаляет все теги с выделенных объектов. |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_SelectTags.png']]     | **Clean Select Tags** | Удаляет все теги того же типа, что и выделенный тег. Поиск ведётся по всей сцене (по всем объектам). |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_Empty_MatTags.png']]  | **Clean Empty Mat-Tags** | Удаляет все теги материалов у которых не назначен материал. Поиск ведётся по всей сцене (по всем объектам). |
| [[ico:'ico/Var_tools/Tools/Clean/Clean_Select_MatTags.png']] | **Clean Select Mat-Tags** | Удаляет все теги материалов с объектов, у которых назначен тот же материал, что и у выделенного тега материала. |
| [[ico:'ico/Var_tools/Tools/Clean/CleanEmptyPolys.png']]      | **Clean Empty Polys** | Удаляет все полигональные объекты `Opolygon`, которые не содержат полигонов. |
::::

### Objects

::::tabs
### Primitivs
| Значок | Плагин | Описание | Галерея |
| ------ | ------ | -------- | ------- |
| [[ico:'ico/Var_tools/Objects/Primitivs/TriCube.png']]             | **Tri Cube** | Генератор куба с 5 типами сетки (треугольники, квады, ёлочка, кирпич, гексагоны), раздельными размерами и подразделениями по XYZ, смещением вершин по нормали и зашивкой швов.| [[mdb:'Типы'-n'TriCube'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/HexSphere.png']]           | **Hex Sphere** | Генератор сферы с настраиваемым числом углов (3–16), радиусом и подразделениями. | [[mdb:'Типы'-n'HexSphere'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/DiamondCylinder.png']]     | **Diamond Cylinder** | Генератор цилиндра с 4 типами сетки (зигзаг/ромбы, спираль, гармошка, прямая), радиусом, высотой, сегментами, крышками, скруткой по оси и смещением вершин по нормали (звезда).| [[mdb:'Типы'-n'DiamondCylinder'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/TriTorus.png']]            | **Tri Torus** | Параметрический тор с расширенными возможностями: • Типы поверхности: Квадратная, Треугольная, Спиральная, Диагональная.  • Деформации: Кручение (Twist), Сужение (Taper), Масштаб.  • Смещение поверхности: Нет / Синусоида / Шум Перлина / Радиальное.  • Детальная настройка фонг-сглаживания | [[mdb:'Типы'-n'TriTorus'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/BrickPlane.png']]          | **Brick Plane** | Плоскость с кирпичной сеткой (паттерны: running bond, stack bond, 1/3 bond, ёлочка, гексагональные, корзинка). Поддерживает швы и displacement по Y. | [[mdb:'Типы'-n'BrickPlane'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/MolecularHexLattice.png']] | **Molecular Hex Lattice** | Генератор молекулярных связей. • Материальные теги: M — шары, T — трубки, F — фаски. | [[mdb:'Превью'-n'MolecularHexLattice'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/Tesseract.png']]           | **Tesseract** | Генератор тессеракта (4D гиперкуб) с проекцией в 3D пространство.  • 16 вершин, 32 ребра, 24 грани, 8 ячеек (кубов) в 4D.  • Поворот в 6 плоскостях 4D пространства (XY, XZ, XW, YZ, YW, ZW).  • Перспективная проекция 4D → 3D.  • Отображение: каркас, рёбра-трубы, вершины, ячейки с прозрачностью.  • Автоматическая анимация вращения. | [[mdb:'Превью'-n'Tesseract'-b8]] |
| [[ico:'ico/Var_tools/Objects/Primitivs/Diamond.png']]             | **Diamond** | Параметрический драгоценный камень с несколькими видами огранки. | [[mdb:'Огранки'-n'Diamond'-b8]] |


### XPressos objects

| Значок | Плагин | Описание |
| ------ | ------ | -------- |
| [[ico:'ico/Var_tools/Objects/XPressos_objects/HierarchyFilter.png']] | **Hierarchy Filter** | Объект-Ноль с расширенными UserData для фильтрации и обхода иерархии. Используется совместно с Xpresso для динамической выборки дочерних объектов. |
::::

### Tegs
::::tabs
### Tegs
| Значок | Плагин | Описание |
| ------ | ------ | -------- |
| [[ico:'ico/Var_tools/Tegs/ChildSelectorTeg.png']]    | **Child Selector Teg** | Добавляет на объект дропдаун выбора прямого дочернего объекта; автоматически обновляет поля «Имя» и «Связь» при смене выбора. |
| [[ico:'ico/Var_tools/Tegs/TargetCamera.png']] [[ico:'ico/Var_tools/Tegs/TargetCameraTag.png']] | **Target Camera** | Создаёт камеру с привязанным Null-таргетом; тег постоянно направляет камеру на таргет, таргет следует за именем камеры и удаляется вместе с тегом. |
| [[ico:'ico/Var_tools/Tegs/CameraVisibilityTag.png']] | **Camera Visibility Tag** | Тег управляет видимостью объекта (вьюпорт + рендер) в зависимости от активной камеры сцены (Stage-объект). |
::::

### Deformers
::::tabs
### Deformers
| Значок | Плагин | Описание |
| ------ | ------ | -------- |
| [[ico:'ico/Var_tools/Deformers/PolySubdivide.png']] | **Poly Subdivider** | Эксперементальный аналог Divider: несколько алгоритмов разбиения полигонов с возможностью лёгкого добавления новых типов. |
::::

:::warning
Плагины протестированы на версии R26.
:::



:::info
Папка плагинов Cinema 4D на Windows: `C:\Users\<имя>\AppData\Roaming\Maxon\Cinema 4D R2024\plugins`
:::



<mdc-n'shift_anim_to_zero'-s550*500>
icon: ico/Var_tools/Animation/shift_anim_to_zero.png
title: Shift Animation2Zero
tagline: Cдвигает все ключевые кадры сцены так, чтобы анимация начиналась с нужного кадра.

Первый ключевой кадр: -35 [["4"]] Последний ключевой кадр: 85
---
Начало анимации (кадр): [[tif:'5'-t'0'-s286]]
Статичных кадров в начале: [[tif:'10'-t'0'-s260]]
Статичных кадров в конце: [[tif:'10'-t'0'-s270]]
[[tif:'Таймлайн начало:                  0'-s488-r0]]
[[tif:'Анимация начало:                  15'-s488-r0]]
[[tif:'Анимация конец:                    135'-s488-r0]]
[[tif:'Таймлайн конец:                    145'-s488-r0]]
---
[["40"]] [[mdb:'OK'-n'0'-s50]] [[mdb:'Отмена'-n'0'-s90]]

::::details
Скриншот
===photo -s500*350
[[p:'image/var_tools/ShiftAnim2Zero.png']]
===
::::
</mdc>

<mdc-n'scale_anim_timeline'-s550*500>
icon: ico/Var_tools/Animation/scale_anim_timeline.png
title: Scale Animation Timeline
tagline: Масштабирует анимацию и весь таймлайн сцены пропорционально относительно нуля, мгновенно растягивая или сжимая длительность по введённому новому количеству кадров.

Текущий таймлайн: 0–95 [["4"]] Анимация: -35-85
---
Новая длина таймлайна (кадров): [[tif:'190'-t'0'-s220]]
[["42"]] [[mdb:'x0.5'-n'0'-s60]] [[mdb:'x2'-n'0'-s40]]
---
[[tif:'Таймлайн начало:                  0'-s488-r0]]
[[tif:'Анимация начало:                  15'-s488-r0]]
[[tif:'Анимация конец:                    135'-s488-r0]]
[[tif:'Таймлайн конец:                    145'-s488-r0]]
[[tif:'Коэффициент:                         x2'-s488-r0]]
---
[["40"]] [[mdb:'OK'-n'0'-s50]] [[mdb:'Отмена'-n'0'-s90]]

::::details
Скриншот
===photo -s500*350
[[p:'image/var_tools/ScaleAnimTimeline.png']]
===
::::
</mdc>


<mdc-n'TriCube'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/TriCube.png
title: Tri Cube
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\TriCube\1.png']]
[[p:'image\var_tools\Objects\Primitivs\TriCube\2.png']]
[[p:'image\var_tools\Objects\Primitivs\TriCube\3.png']]
[[p:'image\var_tools\Objects\Primitivs\TriCube\4.png']]
[[p:'image\var_tools\Objects\Primitivs\TriCube\5.png']]
===
---

## Интерфейс
---
::::details-open
ПАРАМЕТРЫ

♦ Размер X             [["20"]] [[tif:'200'-t'0'-p'cm'-s80]]
♦ Размер Y             [["20"]] [[tif:'200'-t'0'-p'cm'-s80]]
♦ Размер Z             [["20"]] [[tif:'200'-t'0'-p'cm'-s80]]
♦ Подразделения X      [["6"]]  [[tif:'3'-t'0'-s110]]
♦ Подразделения Y      [["6"]]  [[tif:'3'-t'0'-s110]]
♦ Подразделения Z      [["6"]]  [[tif:'3'-t'0'-s110]]
♦ Поверхность          [["14"]] [[ddl:'Треугольники','Квады','Ёлочка','Смещённые ряды','Гексагоны'-s300-p1]]
♦ Смещение (звезда)    [["3"]]  [[biil:-c0-r1]]
♦ Величина смещения    [["1"]]  [[tif:'0'-t'0'-p'cm'-s80]]
♦ Закрыть швы          [["14"]] [[biil:-c0-r1]]
::::
</mdc>
<mdc-n'HexSphere'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/HexSphere.png
title: Hex Sphere
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\HexSphere\1.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\2.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\3.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\4.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\5.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\6.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\7.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\8.png']]
[[p:'image\var_tools\Objects\Primitivs\HexSphere\9.png']]
===
---

## Интерфейс
---
::::details-open
ПАРАМЕТРЫ

♦ Радиус         [["20"]] [[tif:'100'-t'0'-p'cm'-s80]]
♦ Подразделения  [["5"]]  [[tif:'2'-t'0'-s110]]
♦ углов          [["23"]] [[tif:'6'-t'0'-s110]]
::::
</mdc>
<mdc-n'DiamondCylinder'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/DiamondCylinder.png
title: Diamond Cylinder
===photo -s500*300 -c2  -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\DiamondCylinder\1.png']]
[[p:'image\var_tools\Objects\Primitivs\DiamondCylinder\2.png']]
[[p:'image\var_tools\Objects\Primitivs\DiamondCylinder\3.png']]
[[p:'image\var_tools\Objects\Primitivs\DiamondCylinder\4.png']]
[[p:'image\var_tools\Objects\Primitivs\DiamondCylinder\5.png']]
[[p:'image\var_tools\Objects\Primitivs\DiamondCylinder\6.png']]
===
---

## Интерфейс
---
::::details-open
ПАРАМЕТРЫ

♦ Радиус                   [["35"]] [[tif:'100'-t'0'-p'cm'-s80]]
♦ Высота                   [["35"]] [[tif:'200'-t'0'-p'cm'-s80]]
♦ Сегменты (окружность)    [["6"]]  [[tif:'12'-t'0'-s110]]
♦ Сегменты (высота)        [["14"]] [[tif:'6'-t'0'-s110]]
♦ Крышки                   [["35"]] [[biil:-c1-r1]]
♦ Тип поверхности          [["18"]] [[ddl:'Зигзаг (ромбы)','Спираль','Гармошка','Прямая сетка'-s250-p1]]
♦ Скрутка (°)              [["28"]] [[tif:'0'-t'0'-p'°'-s80]]
♦ Смещение (звезда)        [["14"]] [[biil:-c0-r1]]
♦ Величина смещения        [["11"]] [[tif:'20'-t'0'-p'cm'-s80]]
::::
</mdc>
<mdc-n'TriTorus'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/TriTorus.png
title: Tri Torus
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\TriTorus\1.png']]
[[p:'image\var_tools\Objects\Primitivs\TriTorus\2.png']]
[[p:'image\var_tools\Objects\Primitivs\TriTorus\3.png']]
[[p:'image\var_tools\Objects\Primitivs\TriTorus\4.png']]
[[p:'image\var_tools\Objects\Primitivs\TriTorus\5.png']]
[[p:'image\var_tools\Objects\Primitivs\TriTorus\6.png']]
[[p:'image\var_tools\Objects\Primitivs\TriTorus\7.png']]
===
---

## Интерфейс
::::details-open
ОСНОВНЫЕ

♦ Радиус (большой)         [["6"]]  [[tif:'150'-t'0'-p'cm'-s80]]
♦ Радиус (малый)           [["10"]] [[tif:'50'-t'0'-p'cm'-s80]]
♦ Сегменты (кольцо)        [["4"]]  [[tif:'24'-t'0'-s110]]
♦ Сегменты (труба)         [["6"]]  [[tif:'12'-t'0'-s110]]
♦ Тип поверхности          [["7"]]  [[ddl:'Квадратная','Треугольная','Спиральная','Диагональная'-s250-p1]]
::::
::::details-open
ДЕФОРМАЦИИ

♦ Кручение (Twist)         [["8"]]  [[tif:'0'-t'0'-p'°'-s80]]
♦ Сужение X (Taper)        [["5"]]  [[tif:'0'-t'0.0'-s110]]
♦ Сужение Y (Taper)        [["5"]]  [[tif:'0'-t'0.0'-s110]]
♦ Масштаб X                [["18"]] [[tif:'1'-t'0.0'-s110]]
♦ Масштаб Y                [["18"]] [[tif:'1'-t'0.0'-s110]]
♦ Масштаб Z                [["18"]] [[tif:'1'-t'0.0'-s110]]
::::
::::details-open
СМЕЩЕНИЕ ПОВЕРХНОСТИ

♦ Тип смещения             [["15"]] [[ddl:'Нет','Синусоида','Шум Перлина','Радиальное'-s250-p1]]
♦ Амплитуда                [["21"]] [[tif:'0'-t'0'-p'cm'-s80]]
♦ Частота                  [["26"]] [[tif:'0.1'-t'0.0'-s110]]
♦ Фаза (анимировать)       [["5"]]  [[tif:'0'-t'0.0'-s110]]
♦ Октавы шума              [["16"]] [[tif:'4'-t'0'-s110]]
♦ Лакунарность             [["15"]] [[tif:'2'-t'0.0'-s110]]
♦ Усиление (Gain)          [["12"]] [[tif:'0.5'-t'0.0'-s110]]
::::
::::details-open
СПИРАЛЬ

♦ Количество витков        [["5"]]  [[tif:'1'-t'0'-s110]]
♦ Направление              [["15"]] [[ddl:'По часовой','Против часовой'-s250-p1]]
::::
::::details-open
ФОНГ

♦ Угол фонга (°)           [["12"]] [[tif:'180'-t'0'-p'°'-s80]]
♦ Ограничение угла         [["5"]]  [[biil:-c1-r1]]
::::
</mdc>
<mdc-n'BrickPlane'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/BrickPlane.png
title: Brick Plane
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\1.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\2.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\3.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\4.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\5.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\6.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\7.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\8.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\9.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\10.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\11.png']]
[[p:'image\var_tools\Objects\Primitivs\BrickPlane\12.png']]
===
---

## Интерфейс
---
::::details-open
ПАРАМЕТРЫ

♦ Ширина                   [["23"]] [[tif:'400'-t'0'-p'cm'-s80]]
♦ Высота                   [["24"]] [[tif:'400'-t'0'-p'cm'-s80]]
♦ Рядов (X)                [["20"]] [[tif:'4'-t'0'-s110]]
♦ Рядов (Y)                [["20"]] [[tif:'4'-t'0'-s110]]
♦ Тип поверхности          [["7"]]  [[ddl:'Кирпич (1/2)','Кирпич (стек)','Кирпич (1/3)','Ёлочка','Гексагональные','Корзинка'-s200-p1]]
♦ Скрутка (°)              [["17"]] [[tif:'0'-t'0'-p'cm'-s80]]
♦ Величина смещения        [["1"]]  [[tif:'0'-t'0'-s110]]
::::
</mdc>
<mdc-n'MolecularHexLattice'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/MolecularHexLattice.png
title: Molecular Hex Lattice
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\MolecularHexLattice\1.png']]
[[p:'image\var_tools\Objects\Primitivs\MolecularHexLattice\2.png']]
[[p:'image\var_tools\Objects\Primitivs\MolecularHexLattice\3.png']]
[[p:'image\var_tools\Objects\Primitivs\MolecularHexLattice\4.png']]
[[p:'image\var_tools\Objects\Primitivs\MolecularHexLattice\5.png']]
[[p:'image\var_tools\Objects\Primitivs\MolecularHexLattice\6.png']]
===
---

## Интерфейс
::::details-open
КАРКАС (LATTICE)

♦ Размер X                     [["37"]] [[tif:'401'-t'0'-p'cm'-s80]]
♦ Размер Y                     [["37"]] [[tif:'401'-t'0'-p'cm'-s80]]
♦ Размер Z                     [["37"]] [[tif:'401'-t'0'-p'cm'-s80]]
♦ Плотность (шаг сетки)        [["14"]] [[tif:'200'-t'0'-p'cm'-s80]]
♦ Макс. длина связи            [["21"]] [[tif:'250'-t'0'-p'cm'-s80]]
♦ Seed                         [["45"]] [[tif:'0'-t'0'-s110]]
♦ Джиттер (шум позиций)        [["11"]] [[tif:'0'-t'0'-p'cm'-s80]]
♦ Скрывать одиночные шары      [["5"]]  [[biil:-c1-r1]]
::::
::::details-open
STRIP - ВОЛНОВОЕ СМЕЩЕНИЕ

♦ Амплитуда                    [["22"]] [[tif:'0'-t'0'-p'cm'-s80]]
♦ Частота                      [["27"]] [[tif:'0.01'-t'0.0'-s110]]
♦ Фаза (анимировать)           [["5"]]  [[tif:'0'-t'0'-s110]]
♦ Ось волны                    [["22"]] [[ddl:'X (смещение Y)','Y (смещение X)','Z (смещение Y)'-s200-p2]]
::::
::::details-open
ШАРЫ [M]

♦ Радиус шара                  [["10"]] [[tif:'35'-t'0'-p'cm'-s80]]
♦ Подразделение                [["5"]]  [[tif:'1'-t'0'-s110]]
♦ Фонг шаров (°)               [["6"]]  [[tif:'35'-t'0'-p'°'-s80]]
::::
::::details-open
ТРУБКИ [T]

♦ Радиус трубки                [["19"]] [[tif:'6'-t'0'-p'cm'-s80]]
♦ Сегменты окружности          [["5"]]  [[tif:'9'-t'0'-s110]]
♦ Сегменты длины               [["15"]] [[tif:'2'-t'0'-s110]]
::::
::::details-open
ФАСКА [F]

♦ Размер фаски                 [["20"]] [[tif:'3'-t'0'-p'cm'-s80]]
♦ Подразделение фаски          [["5"]]  [[tif:'0'-t'0'-s110]]
::::
</mdc>
<mdc-n'Tesseract'-s600*500>
icon: ico/Var_tools/Objects/Primitivs/Tesseract.png
title: Tesseract
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\Tesseract\1.png']]
[[p:'image\var_tools\Objects\Primitivs\Tesseract\2.png']]
===
---

## Интерфейс
::::details-open
ОСНОВНОЕ

♦ Размер                   [["30"]] [[tif:'200'-t'0'-p'cm'-s80]]
♦ Расстояние проекции      [["5"]]  [[tif:'400'-t'0'-p'cm'-s80]]
♦ Отображение              [["19"]] [[ddl:'Каркас','Рёбра + Вершины','Ячейки','Всё'-s200-p2]]
::::
::::details-open
ПОВОРОТ 4D

♦ Поворот XY               [["6"]]  [[tif:'0'-t'0'-p'°'-s80]]
♦ Поворот XZ               [["6"]]  [[tif:'0'-t'0'-p'°'-s80]]
♦ Поворот XW               [["5"]]  [[tif:'0'-t'0'-p'°'-s80]]
♦ Поворот YZ               [["6"]]  [[tif:'0'-t'0'-p'°'-s80]]
♦ Поворот YW               [["5"]]  [[tif:'0'-t'0'-p'°'-s80]]
♦ Поворот ZW               [["5"]]  [[tif:'0'-t'0'-p'°'-s80]]
::::
::::details-open
АВТОВРАЩЕНИЕ

♦ Включить                 [["12"]] [[biil:-c0-r1]]
♦ Скорость XY              [["6"]]  [[tif:'0'-t'0'-s110]]
♦ Скорость XZ              [["6"]]  [[tif:'0'-t'0'-s110]]
♦ Скорость XW              [["5"]]  [[tif:'0'-t'0'-s110]]
♦ Скорость YZ              [["6"]]  [[tif:'0'-t'0'-s110]]
♦ Скорость YW              [["5"]]  [[tif:'0'-t'0'-s110]]
♦ Скорость ZW              [["5"]]  [[tif:'1'-t'0'-s110]]
♦ Фаза                     [["20"]] [[tif:'0'-t'0'-s110]]
::::
::::details-open
ВИЗУАЛ

♦ Радиус рёбер             [["12"]] [[tif:'5'-t'0'-p'cm'-s80]]
♦ Сегменты рёбер           [["7"]]  [[tif:'9'-t'0'-s110]]
♦ Радиус вершин            [["9"]]  [[tif:'10'-t'0'-p'cm'-s80]]
♦ Сегменты вершин          [["4"]]  [[tif:'8'-t'0'-s110]]
♦ Показать ячейки          [["7"]]  [[biil:-c0-r1]]
::::
</mdc>
<mdc-n'Diamond'-s700*500>
icon: ico/Var_tools/Objects/Primitivs/Diamond.png
title: Diamond
===photo -s500*300 -c2 -asc1000 -asp1000
[[p:'image\var_tools\Objects\Primitivs\Diamond\Asscher.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Brilliant.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Brilliant2.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Cushion.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Emerald.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Heart.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Marquise.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Oval.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Pear.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Princess.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Rose.png']]
[[p:'image\var_tools\Objects\Primitivs\Diamond\Trillion.png']]
===
---

## Интерфейс
::::details-open
ПАРАМЕТРЫ

♦ Огранка              [["23"]] [[ddl:'Бриллиант (Круглая)','Бриллиант (Квадратная)','Принцесса (Квадратная)','Изумруд (Ступенчатая)','Маркиза (Навет)','Груша (Teardrop)','Овал','Кушон (Подушка)','Ашер (Квадрат-ступени)','Сердце','Роза (Старинная)','Триллион (Треугольный)'-s200]]
♦ Размер               [["25"]] [[tif:'100'-t'0'-p'cm'-s80-sc250-d20/200-st1]]
♦ Высота               [["25"]] [[tif:'65'-t'0'-p'cm'-s80-sc250-d20/200-st1]]
♦ Высота короны (%)    [["4"]]  [[tif:'35'-t'0'-p'%'-s80-sc250-d5/60-st1]]
♦ Рундист              [["23"]] [[tif:'3'-t'0.0'-p'cm'-s80-sc250-d0.5/10-st0.5]]
♦ Грани                [["27"]] [[tif:'32'-t'0'-s110-sc250-d8/128-st1]]
♦ Площадка (%)         [["12"]] [[tif:'55'-t'0'-p'%'-s80-sc250-d5/95-st1]]
♦ Калета (%)           [["18"]] [[tif:'0'-t'0'-p'%'-s80-sc250-d0/30-st1]]
♦ Ступени              [["22"]] [[tif:'2'-t'0'-s110-sc250-d2/5-st1]]
::::
</mdc>
