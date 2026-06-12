import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...models import DialogueNode, AnswerOption, Letter, UserAnswer


ALLOWED_SPEAKERS = {"cat", "user", "system"}


@dataclass
class DialogueOptionIn:
    text: str
    next_node_code: Optional[str]
    is_end: bool


@dataclass
class DialogueNodeIn:
    code: str
    day_index: int
    order: int
    speaker: str
    text: str
    options: List[DialogueOptionIn]


def _read_json(path_str: str) -> Any:
    path = Path(path_str)
    if not path.exists():
        raise CommandError(f"Файл не найден: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CommandError(f"Ошибка JSON в {path}: {e}") from e


def _as_int(value: Any, field: str) -> int:
    if not isinstance(value, int):
        raise CommandError(f"Поле '{field}' должно быть int, получено: {type(value).__name__}")
    return value


def _as_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"Поле '{field}' должно быть непустой строкой")
    return value


def _as_opt_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise CommandError(f"Поле 'is_end' должно быть boolean, получено: {type(value).__name__}")


def _parse_dialogues(dialogues_raw: Any) -> List[DialogueNodeIn]:
    if not isinstance(dialogues_raw, list):
        raise CommandError("dialogues.json должен быть JSON-массивом (list)")

    seen_codes = set()
    seen_day_order = set()

    parsed: List[DialogueNodeIn] = []
    for idx, item in enumerate(dialogues_raw):
        if not isinstance(item, dict):
            raise CommandError(f"dialogues[{idx}] должен быть объектом (dict)")

        code = _as_str(item.get("code"), f"dialogues[{idx}].code")
        if code in seen_codes:
            raise CommandError(f"Дублирующийся code: {code}")
        seen_codes.add(code)

        day_index = _as_int(item.get("day_index"), f"dialogues[{idx}].day_index")
        order = _as_int(item.get("order"), f"dialogues[{idx}].order")

        key = (day_index, order)
        if key in seen_day_order:
            raise CommandError(f"Дублирующийся (day_index, order): {key}")
        seen_day_order.add(key)

        speaker = _as_str(item.get("speaker"), f"dialogues[{idx}].speaker")
        if speaker not in ALLOWED_SPEAKERS:
            raise CommandError(
                f"dialogues[{idx}].speaker='{speaker}' невалиден. Допустимо: {sorted(ALLOWED_SPEAKERS)}"
            )

        text = _as_str(item.get("text"), f"dialogues[{idx}].text")

        options_raw = item.get("options", [])
        if options_raw is None:
            options_raw = []
        if not isinstance(options_raw, list):
            raise CommandError(f"dialogues[{idx}].options должен быть list")

        options: List[DialogueOptionIn] = []
        for j, opt in enumerate(options_raw):
            if not isinstance(opt, dict):
                raise CommandError(f"dialogues[{idx}].options[{j}] должен быть dict")

            opt_text = _as_str(opt.get("text"), f"dialogues[{idx}].options[{j}].text")
            next_code = opt.get("next_node_code", None)
            if next_code is not None and not isinstance(next_code, str):
                raise CommandError(
                    f"dialogues[{idx}].options[{j}].next_node_code должен быть string или null"
                )
            is_end = _as_opt_bool(opt.get("is_end"), default=False)

            # Небольшая sanity-проверка
            if is_end and next_code is not None:
                # не запрещаем, но предупреждаем позже при импорте
                pass

            options.append(DialogueOptionIn(text=opt_text, next_node_code=next_code, is_end=is_end))

        parsed.append(
            DialogueNodeIn(
                code=code,
                day_index=day_index,
                order=order,
                speaker=speaker,
                text=text,
                options=options,
            )
        )

    # Проверим, что все ссылки next_node_code существуют среди code
    code_set = {n.code for n in parsed}
    broken: List[Tuple[str, str]] = []
    for n in parsed:
        for opt in n.options:
            if opt.next_node_code and opt.next_node_code not in code_set:
                broken.append((n.code, opt.next_node_code))

    if broken:
        details = ", ".join([f"{src} -> {dst}" for src, dst in broken[:10]])
        more = "" if len(broken) <= 10 else f" (+ещё {len(broken) - 10})"
        raise CommandError(f"Найдены битые next_node_code: {details}{more}")

    return parsed


def _parse_letters(letters_raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(letters_raw, list):
        raise CommandError("letters.json должен быть JSON-массивом (list)")

    seen_day = set()
    parsed: List[Dict[str, Any]] = []
    for idx, item in enumerate(letters_raw):
        if not isinstance(item, dict):
            raise CommandError(f"letters[{idx}] должен быть dict")

        day_index = _as_int(item.get("day_index"), f"letters[{idx}].day_index")
        if day_index in seen_day:
            raise CommandError(f"Дублирующийся day_index в письмах: {day_index}")
        seen_day.add(day_index)

        title = item.get("title", "")
        if title is None:
            title = ""
        if not isinstance(title, str):
            raise CommandError(f"letters[{idx}].title должен быть string")

        text = _as_str(item.get("text"), f"letters[{idx}].text")

        parsed.append({"day_index": day_index, "title": title, "text": text})

    return parsed


class Command(BaseCommand):
    help = "Импорт писем и диалогов из JSON (code/next_node_code)."

    def add_arguments(self, parser):
        parser.add_argument("--dialogues", type=str, required=True, help="Путь к dialogues.json")
        parser.add_argument("--letters", type=str, required=True, help="Путь к letters.json")
        parser.add_argument("--create-user", action="store_true", help="Создать пользователя из env переменных")
        parser.add_argument(
            "--reset-options",
            action="store_true",
            help="Удалить и пересоздать AnswerOption для импортируемых узлов (может удалить UserAnswer!).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только валидация JSON, без записи в БД.",
        )

    def handle(self, *args, **opts):
        dialogues_raw = _read_json(opts["dialogues"])
        letters_raw = _read_json(opts["letters"])

        dialogues = _parse_dialogues(dialogues_raw)
        letters = _parse_letters(letters_raw)

        # Покажем краткий summary до записи
        day_set = sorted({n.day_index for n in dialogues} | {l["day_index"] for l in letters})
        self.stdout.write(self.style.NOTICE(f"Дней в импорте: {day_set}"))
        self.stdout.write(self.style.NOTICE(f"Узлов диалога: {len(dialogues)}"))
        self.stdout.write(self.style.NOTICE(f"Писем: {len(letters)}"))

        if opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS("dry-run: JSON валиден ✅ (запись в БД не выполнялась)"))
            return

        reset_options: bool = bool(opts["reset_options"])

        with transaction.atomic():
            # 1) letters
            letters_created = 0
            letters_updated = 0
            for l in letters:
                obj, created = Letter.objects.update_or_create(
                    day_index=l["day_index"],
                    defaults={"title": l["title"], "text": l["text"]},
                )
                letters_created += 1 if created else 0
                letters_updated += 0 if created else 1

            # 2) nodes
            code_to_node: Dict[str, DialogueNode] = {}
            nodes_created = 0
            nodes_updated = 0

            for n in dialogues:
                node, created = DialogueNode.objects.update_or_create(
                    day_index=n.day_index,
                    order=n.order,
                    defaults={"speaker": n.speaker, "text": n.text},
                )
                code_to_node[n.code] = node
                nodes_created += 1 if created else 0
                nodes_updated += 0 if created else 1

            # 3) options
            options_created = 0
            options_updated = 0
            warnings = 0

            # если reset_options — проверим, не удалим ли UserAnswer
            if reset_options:
                affected_nodes = [code_to_node[n.code].id for n in dialogues]
                if UserAnswer.objects.filter(dialogue_node_id__in=affected_nodes).exists():
                    self.stdout.write(
                        self.style.WARNING(
                            "ВНИМАНИЕ: --reset-options удалит AnswerOption и каскадно удалит UserAnswer для этих узлов."
                        )
                    )

            # подготовим быстрый поиск существующих options по node_id
            existing_by_node: Dict[int, List[AnswerOption]] = {}
            if not reset_options:
                node_ids = [code_to_node[n.code].id for n in dialogues]
                for opt in AnswerOption.objects.filter(dialogue_node_id__in=node_ids).select_related("next_node"):
                    existing_by_node.setdefault(opt.dialogue_node_id, []).append(opt)

            for n in dialogues:
                node = code_to_node[n.code]

                if reset_options:
                    node.options.all().delete()

                # для “мягкого” режима: будем матчить по text (первое неиспользованное совпадение)
                used_existing_ids = set()

                for opt_in in n.options:
                    next_node = code_to_node.get(opt_in.next_node_code) if opt_in.next_node_code else None

                    if opt_in.is_end and next_node is not None:
                        warnings += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Предупреждение: option is_end=true, но next_node_code задан "
                                f"({n.code} -> {opt_in.next_node_code}). Я оставлю next_node, как указано."
                            )
                        )

                    if reset_options:
                        AnswerOption.objects.create(
                            dialogue_node=node,
                            text=opt_in.text,
                            next_node=next_node,
                            is_end=opt_in.is_end,
                        )
                        options_created += 1
                        continue

                    # мягкий upsert по тексту
                    candidates = [o for o in existing_by_node.get(node.id, []) if o.text == opt_in.text and o.id not in used_existing_ids]
                    if candidates:
                        o = candidates[0]
                        used_existing_ids.add(o.id)
                        changed = False
                        if o.is_end != opt_in.is_end:
                            o.is_end = opt_in.is_end
                            changed = True
                        if o.next_node_id != (next_node.id if next_node else None):
                            o.next_node = next_node
                            changed = True
                        if changed:
                            o.save(update_fields=["is_end", "next_node"])
                            options_updated += 1
                    else:
                        AnswerOption.objects.create(
                            dialogue_node=node,
                            text=opt_in.text,
                            next_node=next_node,
                            is_end=opt_in.is_end,
                        )
                        options_created += 1
            
            if opts["create_user"]:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                
                username = os.environ.get("APP_USER_USERNAME")
                password = os.environ.get("APP_USER_PASSWORD")
                
                if not username or not password:
                    self.stdout.write(self.style.WARNING("APP_USER_USERNAME или APP_USER_PASSWORD не заданы — пропускаем создание пользователя"))
                else:
                    user, created = User.objects.get_or_create(username=username)
                    if created:
                        user.set_password(password)
                        user.save()
                        self.stdout.write(self.style.SUCCESS(f"Пользователь '{username}' создан ✅"))
                    else:
                        self.stdout.write(self.style.NOTICE(f"Пользователь '{username}' уже существует — пропускаем"))
                # 2. ДОБАВЛЕНО: Создание пользователя Stas
                stas_username = "Stas"
                stas_password = "stas2212"  # Замени на нужный пароль
                
                stas_user, stas_created = User.objects.get_or_create(username=stas_username)
                if stas_created:
                    stas_user.set_password(stas_password)
                    stas_user.save()
                    self.stdout.write(self.style.SUCCESS(f"Пользователь '{stas_username}' создан ✅"))
                else:
                    self.stdout.write(self.style.NOTICE(f"Пользователь '{stas_username}' уже существует — пропускаем"))

        self.stdout.write(self.style.SUCCESS("Импорт завершён ✅"))
        self.stdout.write(
            f"Letters: created={letters_created}, updated={letters_updated}\n"
            f"Nodes: created={nodes_created}, updated={nodes_updated}\n"
            f"Options: created={options_created}, updated={options_updated}\n"
            f"Warnings: {warnings}"
        )
