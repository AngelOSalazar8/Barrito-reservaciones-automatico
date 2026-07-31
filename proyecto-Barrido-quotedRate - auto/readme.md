

# Seccion de **Automatizacion** del json

### Prueba

 `Tipo` : True/False

Activa o desactiva el modo de prueba
+ `true` → El proceso corre completo (SQL  Wizard) pero no escribe nada en la BD. Ideal para validar que todo funciona sin riesgo.
+ `false` → Modo producción. Sube los datos a dbo.Barrido_quoted al terminar.

---
### days_back
`Tipo`: numero entero positivo (1, 2, 3...)

Valor de respaldo. Cuantos dias atras va la consulta SQL si el dia actual
no esta definido en `days_back_por_dia` (ver abajo).

+ `1` → trae reservas del dia de ayer.
+ `3` → trae los ultimos 3 dias.

---
### days_back_por_dia
`Tipo`: objeto JSON con claves `"0"` a `"6"` (dia de la semana de Python)

Permite definir cuantos dias atras se consultan **segun el dia en que corre el proceso**.
Tiene prioridad sobre `days_back`. Si un dia no aparece en el mapa, se usa `days_back`.

| Clave | Dia      | Valor recomendado |
|-------|----------|-------------------|
| `"0"` | Lunes    | `3` (cubre vie + sab + dom) |
| `"1"` | Martes   | `1` |
| `"2"` | Miercoles | `1` |
| `"3"` | Jueves   | `1` |
| `"4"` | Viernes  | `1` |
| `"5"` | Sabado   | (no se usa si el programador corre lun-vie) |
| `"6"` | Domingo  | (no se usa si el programador corre lun-vie) |

> Configuracion actual: el Programador de Windows ejecuta de lunes a viernes.
> El lunes jala 3 dias para cubrir el fin de semana perdido por inestabilidad de red.

---
### min_reservas
`Tipo`: número entero (100, 150…)

Mínimo de reservas que debe regresar la consulta SQL para que el proceso continúe.

+ Si la consulta trae menos de este número, el script asume que la data aún no está disponible y espera antes de reintentar.
> Rango normal de operación: 100–300. Se recomienda dejarlo en 100.

---
### espera_min_reservas_seg
`Tipo`: segundos (300 = 5 minutos)

Cuánto tiempo espera el script entre cada reintento cuando el número de reservas no alcanza el mínimo.

+ `300` → espera 5 minutos antes de volver a consultar SQL.
> Si la data tarda en llegar, puedes subirlo a 600 (10 min).

---
### reintentos_min_reservas
`Tipo`: número entero (5, 3, 10…)

Cuántas veces reintenta la consulta SQL si no llega al mínimo de reservas antes de rendirse y mandar correo.

>Con los valores por defecto: esperará hasta 5 × 5 min = 25 minutos antes de abortar y notificarte.


---
### reintentos_terminal
`Tipo`: número entero (10, 5…)

Cuántos intentos hace para reconectar BlueZone si detecta que la terminal se desconectó (ya sea al inicio o durante el barrido).

>Si todos los intentos fallan, manda correo de alerta y aborta.

---
### espera_terminal_seg
`Tipo`: segundos (60 = 1 minuto)

Cuánto espera entre cada intento de reconexión de BlueZone.

> Con los valores por defecto: esperará hasta 10 × 60 seg = 10 minutos antes de declarar la terminal como inaccesible.

---
