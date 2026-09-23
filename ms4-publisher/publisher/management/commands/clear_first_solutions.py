from django.core.management.base import BaseCommand
from django.db.models import Q
from publisher.models import FirstSolutionEvent, ExecutionLog


class Command(BaseCommand):
    help = "Elimina registros de FirstSolutionEvent de la base de datos para permitir volver a publicarlos."

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Elimina TODOS los registros de First Solution en la base de datos.',
        )
        parser.add_argument(
            '--contest',
            type=str,
            help='Clave de maratón (ej. 2026/08 o 2026/8).',
        )
        parser.add_argument(
            '--letter',
            type=str,
            help='Letra del problema específico a eliminar (ej. A, B, C...).',
        )

    def handle(self, *args, **options):
        is_all = options.get('all', False)
        contest = options.get('contest')
        letter = options.get('letter')

        if not is_all and not contest and not letter:
            self.stdout.write(self.style.WARNING(
                "Debes especificar al menos uno de los siguientes argumentos:\n"
                "  --all               : Eliminar todos los registros de First Solution.\n"
                "  --contest <año/num> : Eliminar los registros de una maratón (ej. --contest 2026/08).\n"
                "  --letter <letra>    : Eliminar solo un problema específico (ej. --letter A).\n\n"
                "Ejemplo: python manage.py clear_first_solutions --all"
            ))
            return

        qs = FirstSolutionEvent.objects.all()

        if contest:
            parts = contest.strip().split('/')
            if len(parts) == 2:
                y, c = parts[0].strip(), parts[1].strip()
                c_norm = str(int(c)).zfill(2) if c.isdigit() else c
                qs = qs.filter(Q(contest_key=f"{y}/{c}") | Q(contest_key=f"{y}/{c_norm}"))
            else:
                qs = qs.filter(contest_key=contest.strip())

        if letter:
            qs = qs.filter(problem_letter=letter.strip().upper())

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.NOTICE("No se encontraron registros de FirstSolutionEvent que coincidan."))
            return

        qs.delete()

        # Registrar en ExecutionLog para trazabilidad
        ExecutionLog.objects.create(
            user=None,
            contest_key=contest or "ALL",
            rpc_name="SISTEMA",
            pub_type="FIRST_SOLUTION",
            level="WARNING",
            category="FIRST_SOLUTION",
            message=f"🗑️ [CLI] Se eliminaron {count} registro(s) de First Solution de la base de datos (problema: {letter or 'TODOS'}).",
            details={"letter": letter, "contest": contest, "deleted_count": count},
        )

        self.stdout.write(self.style.SUCCESS(f"✓ Se eliminaron {count} registro(s) de FirstSolutionEvent de la base de datos exitosamente."))
