# Manual de demostración del sistema Orbe

Orbe es un servicio ficticio de gestión de registros creado para demostrar la ingesta de documentos y la evaluación del asistente. Los datos de este manual son inventados y sirven únicamente como conjunto de prueba.

## Prueba y cuentas
La prueba gratuita dura 14 días. Durante la prueba se pueden registrar hasta 5 miembros y almacenar 1 GB de documentos.

## Documentos y registros
El servicio acepta archivos CSV y JSON de hasta 25 MB por archivo. Cada registro incluye un cliente, una fecha y un código. Los registros se conservan durante 180 días. La búsqueda no distingue entre mayúsculas y minúsculas y admite hasta 10 palabras clave. Los resultados se pueden exportar en formato CSV o PDF.

## API
La API usa la ruta base `/v1`. La autenticación se realiza con tokens Bearer, que caducan a los 60 minutos. El límite es de 120 solicitudes por minuto. Cuando se supera, la API devuelve HTTP 429 y una cabecera `Retry-After: 30`. Cada lote admite hasta 500 registros. Los identificadores de registro empiezan por `ORB-`.

## Procesamiento
Los estados posibles de un registro son pendiente, procesando, completado y fallido. El servicio realiza hasta 3 reintentos y espera 10 segundos entre ellos.

## Horario y soporte
La zona horaria del servicio es `Europe/Madrid`. El equipo de soporte atiende de lunes a viernes, de 09:00 a 17:00, hora de Madrid. El correo de soporte es `ayuda@orbe.example`.

## Seguridad y copias
Los datos almacenados se cifran con AES-256. Las conexiones usan TLS 1.2. Se hace una copia de seguridad diaria a las 02:00 y cada copia se conserva durante 14 días. Una solicitud de eliminación de datos se completa en un máximo de 7 días naturales.
