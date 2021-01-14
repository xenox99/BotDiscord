from __future__ import print_function
import discord, datetime ,asyncio, time, json, threading, queue, pickle, os.path
import pytz
from discord.ext import commands
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Token del BOT
token = None
with open('rsc/token-discord.txt', 'r') as f:
    token = f.read()

# permisos basicos del BOT
intent = discord.Intents.default()
intent.members = True

#instancia del bot
bot = commands.Bot(command_prefix='>', intents=intent)
bot.remove_command("help")

horaActualizar = 0
default_channel = None
id_owner_bot = None
id_server = None

encuesta = None
id_autor_encuesta = None
reacciones_encuesta = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
reacciones_permitidas = []
reacciones_usuarios = []

cumpleHabilitado = False
calendarHabilitado = False
classroomHabilitado = False

queueMsg = queue.Queue(maxsize = 1)
queueClass = queue.Queue(maxsize = 5)
queueCumple = queue.Queue(maxsize = 5)

WORK = 100
ANNOUNCEMENT = 200
CLASE = 1
CUMPLE = 0

backup_path='rsc/backup.json'
birthday_path = 'rsc/birthday.json'
calendar_path = 'rsc/calendar.json'
commands_path = 'rsc/comandos.json'
config_path = 'rsc/config.json'
links_path = 'rsc/links.json'
works_path = 'rsc/works.json'

#zona horaria base
zonaUTC = pytz.timezone('UTC')



def diferenciaHora(horaProgramada:int):
    """
    devuelve: cantidad de tiempo faltante en segundos para la horaProgramada
    """ 
    horaActual = (datetime.datetime.now()).astimezone(zonaUTC)   #fecha y hora actual
    horaActual =horaActual.hour*3600 + horaActual.minute*60 + horaActual.second # hora actual en segundos
    diferencia = horaActual - horaProgramada #diferencia entre las horas
    if(diferencia > 0):  
        #si es >0 entonces las hora ya paso, por lo que el tiempo que falta 
        #es la resta entre los segundos de un dia y la diferencia
        diferencia = 86400-diferencia
    else:
        #si <= 0 entonces la hora aun no paso, por lo que el 
        # tiempo que falta es el resultado multiplicado por -1
        #rara vez daria resultado =0
        diferencia = diferencia*(-1)
    return diferencia
    
def queueHandler(thread):
    evento = {}
    while calendarHabilitado and thread.is_alive():
        try:
            yield
            num = queueMsg.get_nowait()
            if(num != None):
                if (num == 0):
                    #actualizarCalendar
                    gestionarAlarmasEventos()

                else:
                    with open(calendar_path, 'r') as f:
                        evento = json.load(f)
                    loop = asyncio.get_event_loop()
                    task = loop.create_task(mostrarMensaje(tipo=1, other=evento[num-1]))
                    task
        except queue.Empty:
            pass

def queueHandlerClass(thread):
    while classroomHabilitado and thread.is_alive():
        try:
            yield
            changes = queueClass.get(block = False)
            if changes != None:
                loop = asyncio.get_event_loop()
                if (changes[0] == WORK):
                    #cambios en las tareas
                    task = loop.create_task(mostrarMensaje(tipo=WORK, other=changes[1]))
                    task
                elif (changes[0] == ANNOUNCEMENT):
                    #cambios en los anuncios
                    task = loop.create_task(mostrarMensaje(tipo=ANNOUNCEMENT, other=changes[1]))
                    task
        except queue.Empty:
            pass
        
def queueHandlerCumple(thread):
    while cumpleHabilitado and thread.is_alive():
        try:
            yield
            id_user= queueCumple.get(block=False)
            if id_user != None:
                #hay cumple/s
                for i in id_user:
                    loop = asyncio.get_event_loop()
                    task= loop.create.task(mostrarMensaje(tipo=CUMPLE, other = i))
                    task
        except queue.Empty:
            pass

def matchUserWithDate(idu: int, fecha: str, dbirth: dict):
    """
    Permite saber si el conjunto (ID usuario, fecha) se encuentra en el diccionario dbirth.
    Recibe como parametros:
    idu: int -> ID usuario.
    fecha: string -> fecha de cumple.
    dbith: dict -> diccionario con los valores.
    Retorna True si se encuentra el valor idu en la clave fecha en dbirth.
    Retorna False en cualquier otro caso. En caso de encontrar el valor idu en otra clave y elimina idu de esa clave.
    """
    for k, v in dbirth.items():
        breakIteracion = False  #bandera para saber si hay que romper ambos bucles
        for i in v:
            if(i == idu and k == fecha):
                return True
            elif(i == idu): 
                #si no se encutra el conjunto (id, fecha), 
                #pero si se encuentra el id entonces elimino la ocurrencia
                v.remove(i)
                if(len(dbirth[k]) == 0):    #si queda vacio entonces termino
                    dbirth.pop(k)
                    breakIteracion = True
            if (breakIteracion):
                break
        if(breakIteracion):
            break
    return False

    # with open('birthday.json', 'w') as f:
    #  json.dump(dbirth, f, indent=4)

def getEvents():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('calendar', 'v3', credentials=creds)

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    print('Getting the upcoming 10 events')
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=10, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])
    summary_events = []
    if not events:
        print('No upcoming events found.')
    else:   #si hay eventos, entonces elimino la informacion innecesaria
        for i in events:    #events es una lista de diccionarios
            values = []
            keys = []
            for k,v in i.items():  #controlo cada clave de cada diccionario
                if (k == "hangoutLink" or k == "start" or k == "end" or k == "summary" or k == "description"):
                    values.append(v)
                    keys.append(k)
            summary_events.append(dict(zip(keys,values)))

    with open(calendar_path, 'w') as f:
        json.dump(summary_events, f, indent=4)

def gestionarAlarmasEventos():
    getEvents()
    eventos = []
    with open(calendar_path, 'r') as f:
        eventos = json.load(f)
    eventos_timers = []
    for e in eventos:
        if ('dateTime' in e['start']):    
            hpEvento = ((e["start"])["dateTime"])[11:25]
            hpEvento = datetime.time(hour = int(hpEvento[0:2]), minute= int(hpEvento[3:5]), second= 0)
            hpEvento = hpEvento - datetime.timedelta(hours=3)
            hpEvento = hpEvento.hour*3600 + hpEvento.minute*60
            eventos_timers.append([hpEvento, e])
    for i in eventos_timers:
        if horaActualizar > i[0]:
            eventos_timers.insert(eventos_timers.index(i)+1, [horaActualizar])
            break
    t = hiloCalendar(eventos_timers)
    t.start()
    loop = asyncio.get_event_loop()
    task = loop.create_task(queueHandler(t))
    task

async def mostrarMensaje(tipo:int, other):
    if (tipo==CLASE):
        titulo = "Proxima Clase"
        descripcion = ""
        urlMeet = ""
        if ("summary" in other):
            titulo = other["summary"]
        if ("desciption" in other):
            descripcion=other["description"]
        if ("hangoutLink" in other):
            url = other["url"]
        e = discord.Embed(title=titulo, description=descripcion, url=urlMeet)
        await default_channel.send(embed = e)
    elif (tipo ==CUMPLE):
        member = discord.utils.get(default_channel.guild.members, id=other)
        titulo = 'Feliz Cumpleaños ' + member.mention
        descripcion = 'Cuantos cumplis prro?'
        e = discord.Embed(title=titulo, description=descripcion)
        await default_channel.send(embed = e)
    elif (tipo == ANNOUNCEMENT):
        titulo='Anuncio!!!'
        descripcion= other['text']
        urlAnuncio = other['alternateLink']
        if ('materials' in other):
            descripcion = descripcion + '\n\nMaterial disponible en el Link del titulo'
        e = discord.Embed(title=titulo, description= descripcion, url=urlAnuncio)
        await default_channel.send(embed=e)
    elif (tipo == WORK):
        titulo = 'Trabajo de Clase!!! '
        if ('title' in other):
            titulo = titulo + other['title']
        descripcion = ""
        if ('description' in other):
            descripcion= 'Instrucciones:\n' + other['description']
        urlAnuncio = other['alternateLink']
        if ('materials' in other):
            descripcion = descripcion + '\n\nMaterial disponible en el Link del titulo'
        e = discord.Embed(title=titulo, description= descripcion, url=urlAnuncio)
        if ('dueDate' in other):
            fecha = other['dueDate']
            hora = other['dueTime']
            fecha_entrega = datetime.datetime(fecha[0], fecha[1], fecha[2], hora[0], hora[1]) - datetime.timedelta(hour=3)
            e.add_field(name='Fecha de Entrega', value = fecha_entrega.strftime('Fecha: %d/%m/%Y - Hora:%H:%M'))
        await default_channel.send(embed=e)
    
class hiloCalendar(threading.Thread):
    def __init__(self, eventos_timers):
        # Call the Thread class's init function
        threading.Thread.__init__(self)
        self.eventos_timers = eventos_timers

    def run(self):
        aux = 1
        for i in self.eventos_timers:
            intervalo = diferenciaHora(i[0])
            time.sleep(intervalo)
            tipo = 0
            
            if (type(i[1]) is dict):
                #mensaje evento
                tipo = (self.eventos_timers.index(i)+aux)
            else:
                aux = 2
            queueMsg.put(tipo)
        time.sleep(2)
                
class hiloClassroom(threading.Thread):
    def __init__(self):
        # Call the Thread class's init function
        threading.Thread.__init__(self)
    
    def run(self):
        old_announcements, old_courses, old_works = self.getClassroom()
        new_courses, new_works, new_announcements = [],[],[]
        while True:
            time.sleep(30)
            new_announcements, new_courses, new_works = self.getClassroom()
            works_changes = self.changes(old_works, new_works)
            announcements_changes = self.changes(old_announcements, new_announcements)
            
            if (len(works_changes) >0):
                for w in works_changes:
                    queueClass.put([WORK, w])
                old_works = new_works

            if (len(announcements_changes) >0):
                for a in announcements_changes:
                    queueClass.put([ANNOUNCEMENT,a])
                old_announcements = new_announcements
        time.sleep(2)
    
    def changes(self, old_item, new_item):
        changes_list=[]
        #controlo los modificados
        for o in old_item:
            for n in new_item:
                if (o['id'] == n['id']):
                    if  (o['updateTime'] != n['updateTime']):
                        changes_list.append(n)
                    break
        
        #agrego los sobrantes
        for i in range(len(old_item), len(new_item)):
            changes_list.append(new_item[i])
        return changes_list
        
    def getClassroom(self):
        """Shows basic usage of the Classroom API.
        Prints the names of the first 10 courses the user has access to.
        Returns: [courses], [works], [announcements]
        """
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('tokenclass.pickle'):
            with open('tokenclass.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials-classroom.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('tokenclass.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('classroom', 'v1', credentials=creds)

        # Call the Classroom API
        results = service.courses().list(pageSize=10).execute()
        courses = results.get('courses', [])
        works_list=[]
        announcements_list =[]
        for c in courses:
            works= service.courses().courseWork().list(courseId=c['id'], courseWorkStates='PUBLISHED',
                                                        pageSize=10).execute()
            if len(works):
                works_list.extend(works['courseWork'])
            announcements= service.courses().announcements().list(courseId=c['id'], announcementStates='PUBLISHED',
                                                            pageSize=15).execute()
            if len(announcements):
                announcements_list.extend(announcements['announcements'])
        with open(works_path, 'w') as f:
            json.dump(works_list, f, indent=4)
        return announcements_list, courses, works_list

class hiloCumples(threading.Thread):
    def __init__(self):
        # Call the Thread class's init function
        threading.Thread.__init__(self)
    
    def run(self):
        time.sleep(30)
        global cumpleHabilitado
        while cumpleHabilitado:
            birth = {}
            with open(birthday_path, 'r') as f:
                birth = json.load(f)
            Hoy = datetime.datetime.utcnow()    #fecha y hora hoy
            Hoy = Hoy - datetime.timedelta(hours=3) #fecha y hora Argentina
            fechaHoy = Hoy.strftime('%d/%m/%Y')[0:5]    #transformo la fecha a string
            if fechaHoy in birth.keys():    #verifico si hay un cumpleaños hoy
                horas_alarmas=[0,8,14,18]   #horas a las cuales quiero alarmas
                for i in range(4):
                    horaActual=datetime.datetime.utcnow - datetime.timedelta(hours=3)   #hora actual Argentina
                    if (horaActual.hour == i):  #controlo cada hora de alarma con hora actual
                        queueCumple.put(birth[fechaHoy])    #si coincide entonces envio el mensaje al Handler
                        try:
                            siguienteHora = horas_alarmas.index(i)+1    #obtengo la siguiente hora para dormir el hilo hasta esa hora
                            intervalo = diferenciaHora(horas_alarmas[siguienteHora]*3600)   
                            time.sleep(intervalo)
                        except IndexError:  #la siguiente hora al 18 no existe, asi que debo atrapar la excepcion
                            pass
                    elif(horaActual.hour < i):  #si la hora actual es menor a alguna de las horas, entonces espero hasta esa hora
                        intervalo = diferenciaHora(i*3600)
                        time.sleep(intervalo)
                    #si la hora es mayor a alguna de las programadas, entonces paso a la siguiente
                    #si la hora es mayor a 18, entonces espero hasta las 00 del otro dia
            intervalo = diferenciaHora(0)
            time.sleep(intervalo)
        time.sleep(2)



#COMANDOS DE AYUDA
@bot.group(invoke_without_command=True, aliases=['h'])
async def help(ctx):
    e = discord.Embed(title='Help', description= 'Usa >help <command> para informacion mas detallada de los comandos')
    for c in bot.commands:
        descripcion = c.help
        
        if (not descripcion):
            descripcion = 'nada'
        else:
            descripcion = descripcion.split('.', 1)
            descripcion = descripcion[0]
        e.add_field(name= c.name, value= descripcion, inline=False)
    await ctx.send(embed= e)

@help.command()
async def alink(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['alink']
    e = discord.Embed(title='alink', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def links(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = (commands_dict['links'])
    e = discord.Embed(title='links', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def rol(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = (commands_dict['rol'])
    e = discord.Embed(title='rol', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def conectarCalendar(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = (commands_dict['conectarCalendar'])
    e = discord.Embed(title='conectarCalendar', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def offCalendar(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['offCalendar']
    e = discord.Embed(title='offCalendar', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def conectarClass(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['conectarClass']
    e = discord.Embed(title='conectarClass', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def offClass(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['offClass']
    e = discord.Embed(title='offClass', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def cronograma(ctx):
    commands_dict = {}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['cronograma']
    e = discord.Embed(title='cronograma', description = ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def cumple(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['cumple']
    e = discord.Embed(title='cumple', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def offCumple(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['offCumple']
    e = discord.Embed(title='offCumple', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def cumples(ctx):
    commands_dict = {}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['cumples']
    e = discord.Embed(title= 'cumples', description= ayuda_comandos)
    await ctx.send(embed= e)

@help.command()
async def owner(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['owner']
    e = discord.Embed(title='owner', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def default(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['default']
    e = discord.Embed(title='default', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def encuesta(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['encuesta']
    e = discord.Embed(title='encuesta', description= ayuda_comandos)
    await ctx.send(embed=e)

@help.command()
async def finEncuesta(ctx):
    commands_dict={}
    with open(commands_path, 'r') as f:
        commands_dict = json.load(f)
    ayuda_comandos = commands_dict['finEncuesta']
    e = discord.Embed(title='finEncuesta', description= ayuda_comandos)
    await ctx.send(embed=e)



#COMANDOS UTILITARIOS
@bot.command()
async def alink(ctx, *args):
    """
    Permite guardar links y especificar un tag.
    Recibe como parametros una lista de strings separadas por espacios.
    \n**Sintaxis**:
    >alink <tag>:<link>     -> >alink curso:www.link.com
    >alink <link>           -> >alink www.link.com
    >alink <link1> <link2>  -> >alink www.link1.com www.link2.com
    >alink <tag1>:<link1> <tag2>:<link2>    -> >alink cursos:link1.com juegos:link2.com
    """
    links = []
    for i in args:
        if (i.count(':') > 0):
            i=i.split(':')
            links.append(i)
        else:
            links.append([i])
    savedLinks= {}
    if os.path.exists(links_path):
        with open(links_path) as f:
            savedLinks = json.load(f)
            for i in links:
                if (len(i) > 1):
                    if (i[0] in savedLinks.keys()):
                        savedLinks[i[0]].append(i[1])
                    else: 
                        savedLinks[i[0]] = []
                        savedLinks[i[0]].append(i[1])
                else:
                    savedLinks['Links'].append(i[0])
        with open(links_path, 'w') as f:
            json.dump(savedLinks, f, indent=4)
    else:
        savedLinks['Links'] = []
        for i in links:
            if (len(i) > 1):
                if (i[0] in savedLinks.keys()):
                    savedLinks[i[0]].append(i[1])
                else: 
                    savedLinks[i[0]] = []
                    savedLinks[i[0]].append(i[1])
            else:
                savedLinks['Links'].append(i[0])
        with open(links_path, 'w') as f:
            json.dump(savedLinks, f, indent=4)

@bot.command()
async def links(ctx):
    """
    Permite visualizar los links almacenados.
    \n**Sintaxis**:
    >links
    """
    mensaje = ''
    if (os.path.exists(links_path)):
        links = {}
        with open(links_path) as f:
            links = json.load(f)
        for k,v in links.items():
            mensaje = mensaje + k
            for i in v:
                mensaje = mensaje + '\n' + i
            mensaje = mensaje + '\n\n'
    else:
        mensaje = 'No hay links'
    embed = discord.Embed(tittle='Links', description=mensaje)
    await ctx.send(embed= embed)

@bot.command()
async def offClass(ctx):
    """
    Permite deshabilitar el control del GoogleClassroom (Solo para administrador de bot).
    \n**Sintaxis**:
    >offClass
    """
    global classroomHabilitado
    if (id_owner_bot == ctx.message.author.id):
        classroomHabilitado = False
        await ctx.send('GoogleClassroom deshabilitado')
    else:
        await ctx.send('No tienes permisos para usar este comando')

@bot.command()
async def conectarClass(ctx):
    """
    Permite conectar GoogleClassroom a la aplicación (Solo para administrador de bot).
    \n**Sintaxis**:
    >conectarClass
    """
    global classroomHabilitado
    if (default_channel):
        if (id_owner_bot == ctx.message.author.id):
            if(not classroomHabilitado):
                t = hiloClassroom()
                t.start()
                loop = asyncio.get_event_loop()
                task = loop.create_task(queueHandlerClass(t))
                task
                classroomHabilitado=True
                await ctx.send('conexion a classroom')
            else:
                await ctx.send('Ya se encuentra habilitado')
        else:
            await ctx.send('No tienes permisos para usar este comando')
    else:
        await ctx.send('Se debe setear un canal por defecto primero')

@bot.command()
async def offCalendar(ctx):
    """
    Permite deshabilitar el control de los eventos de GoogleCalendar (Solo para administrador de bot).
    \n**Sintaxis**:
    >offCalendar
    """
    global calendarHabilitado
    if (id_owner_bot == ctx.message.author.id):
        calendarHabilitado = False
        await ctx.send('GoogleCalendar deshabilitado')
    else:
        await ctx.send('No tienes permisos para usar este comando')

@bot.command()
async def conectarCalendar(ctx, hora):
    """
    Permite conectar GoogleCalendar a la aplicación (Solo para administrador de bot).
    \n**Sintaxis**:
    >conectarCalendar <hora> -> >conectarCalendar 1
    *hora*: entero entre 0 y 24
    """
    global calendarHabilitado
    global horaActualizar
    if (default_channel):
        if (id_owner_bot == ctx.message.author.id):
            if(not calendarHabilitado):
                formatoCorrecto = False
                try:
                    hora = datetime.time(hour= int(hora), minute=0, second=0)
                    hora = hora - datetime.timedelta(hours=3)
                    formatoCorrecto = True
                except ValueError:
                    await ctx.send("Formato de hora incorrecto")
                if (formatoCorrecto):
                    calendarHabilitado= True
                    hora = hora.hour*3600 + hora.minute*60
                    horaActualizar = hora
                    gestionarAlarmasEventos()
                await ctx.send('Conexion Exitosa')
            else:
                await ctx.send('Ya se encuentra conectado')
        else:
            await ctx.send('No tienes permisos para usar este comando')
    else:
        await ctx.send('Se debe setear un canal por defecto primero')

@bot.command()
async def cronograma(ctx, *args):
    """
    Permite ver el cronograma.
    \n**Sintaxis**:
    >cronograma hoy  -> para el cronograma del dia de hoy
    >cronograma      -> para el cronograma completo
    """
    e = discord.Embed(title='Cronograma')
    if (args and (calendarHabilitado or classroomHabilitado)):
        vacio = 0
        if (args[0].lower() == 'hoy'):
            if (calendarHabilitado):
                calendar = {}
                try:
                    with open(calendar_path, 'r') as f:
                        calendar = json.load(f)
                except json.JSONDecodeError:
                    vacio+=CLASE
                if (vacio >= CLASE):
                    for e in calendar:
                        fecha_ini = None
                        fecha_fin = None
                        if ('dateTime' in e['start']):
                            fecha_ini = (e['start']['dateTime'][0:15]).replace('T', '-')
                            fecha = datetime.datetime.strptime(fecha_ini, '%Y-%m-%d-%H:%M:%S-%z')
                        elif ('date' in e['start']):
                            fecha_ini = e['start']['date'][0:9]
                            fecha = datetime.datetime.strptime(fecha_ini, '%Y-%m-%d')
                        if (fecha > (datetime.datetime.utcnow() - datetime.timedelta(hours=3))):
                            if ('dateTime' in e['end']):
                                fecha_fin = e['end']['dateTime'][0:15]
                            elif ('date' in e['end']):
                                fecha_fin = e['end']['date'][0:9]
                            descripcion = ''
                            if ('description' in e):
                                descripcion = e['description']
                            descripcion = f'{descripcion}\nInicia: {fecha_ini}\nTermina: {fecha_fin}'
                            e.add_field(name= e['summary'], value= descripcion)
            if (calendarHabilitado):    
                works = []
                try:
                    with open(works_path, 'r') as f:
                        works = json.load(f)
                except json.JSONDecodeError:
                    vacio+=WORK
                if (vacio >= WORK):
                    for w in works:
                        if ('dueDate' in w):
                            fecha_fin = w['dueDate']
                            hora_fin = w['dueTime']
                            fecha = datetime.datetime(year=fecha_fin['year'], month=fecha_fin['month'], day=fecha_fin['day'], 
                                                        hour=hora_fin['hours'], minute=hora_fin['minutes']) 
                            fecha = fecha - datetime.timedelta(hour=3)
                            if (fecha > (datetime.datetime.utcnow() - datetime.timedelta(hours=3))):
                                descripcion = f'Fecha de Entrega: {fecha_fin["day"]}/{fecha_fin["month"]}/{fecha_fin["year"]}, Hora: {hora_fin["hours"]}:{hora_fin["minutes"]}\n'
                                e.add_field(name= w['title'], value=descripcion)
            if (vacio > 0):
                e.description = 'Hoy\n:'
            else:
                e.description = 'No hay eventos para el dia de hoy.'
        else:
            e.title= 'Comando incorrecto.'
            e.description= 'Usa >help cronograma para mas información.'
    elif (calendarHabilitado or classroomHabilitado):
        e.description = 'Funciones no habilitadas.'
    elif (not args):
        vacio = 0
        if (calendarHabilitado):
            calendar = {}
            try:
                with open(calendar_path, 'r') as f:
                   calendar = json.load(f)
            except json.JSONDecodeError:
                vacio+=CLASE
            if (vacio >= CLASE):
                for e in calendar:
                    fecha_ini = None
                    fecha_fin = None
                    if ('dateTime' in e['start']):
                        fecha_ini = (e['start']['dateTime'][0:15]).replace('T', '-')
                    elif ('date' in e['start']):
                        fecha_ini = e['start']['date'][0:9]
                    if ('dateTime' in e['end']):
                        fecha_fin = e['end']['dateTime'][0:15]
                    elif ('date' in e['end']):
                        fecha_fin = e['end']['date'][0:9]
                    descripcion = ''
                    if ('description' in e):
                        descripcion = e['description']
                    descripcion = f'{descripcion}\nInicia: {fecha_ini}\nTermina: {fecha_fin}'
                    e.add_field(name= e['summary'], value= descripcion)
        if (calendarHabilitado):    
            works = []
            try:
                with open(works_path, 'r') as f:
                    works = json.load(f)
            except json.JSONDecodeError:
                vacio+=WORK
            if (vacio >= WORK):
                for w in works:
                    descripcion='Sin fecha de entrega'
                    if ('dueDate' in w):
                        fecha_fin = w['dueDate']
                        hora_fin = w['dueTime']
                        fecha = datetime.datetime(year=fecha_fin['year'], month=fecha_fin['month'], day=fecha_fin['day'], 
                                                    hour=hora_fin['hours'], minute=hora_fin['minutes']) 
                        fecha = fecha - datetime.timedelta(hour=3)
                        if (fecha > (datetime.datetime.utcnow() - datetime.timedelta(hours=3))):
                            descripcion = f'Fecha de Entrega: {fecha_fin["day"]}/{fecha_fin["month"]}/{fecha_fin["year"]}, Hora: {hora_fin["hours"]}:{hora_fin["minutes"]}\n'
                    e.add_field(name= w['title'], value=descripcion)
        if (vacio > 0):
            e.description = 'Proximos eventos\n:'
        else:
            e.description = 'No hay eventos proximos.'
    await ctx.send(embed=e)

@bot.command()
async def ping(ctx):
    """
    Comando de prueba para saber si el bot sigue funcionando.
    \n**Sintaxis**:
    >ping
    """
    await ctx.send('Sigo escuchando')

@bot.command()
async def rol(ctx, rol_to_set):
    """
    Permite autoasignarse un rol. Solo funciona con usuarios que tienen el rol invitado.
    Usuarios que usan esta funcion pierden el rol de invitado.
    \n**Sintaxis**:
    >rol <rol>  ->  >rol usuario
    """
    autor = ctx.message.author  # obtengo el ID del autor del mensaje
    roles_autor = autor.roles   # obtengo los roles que tiene el autor del mensaje
    mensaje = 'Ya tienes un rol asignado. NO puedes tener otro.'
    rol_asignado = False    #bandera para saber si el rol fue asignado
    for r in roles_autor:   #controlo si el autor tiene el rol INVITADO entonces puede usar el comando
        if (r.name == 'invitado'):
            rol = discord.utils.get(ctx.guild.roles, name=rol_to_set) # obtengo el rol especificado en rol_to_set
            if (rol):
                await autor.add_roles(rol) #seteo el rol al autor del mensaje
                mensaje = f'Ahora eres parte de {rol.name}. {autor.mention}'
                rol_asignado = True #el rol fue asignado
                await autor.remove_roles(r)   #remuevo el rol invitado del usuario que adquirio el nuevo rol
            else:
                mensaje = 'Rol inexistente.'
    await ctx.send(mensaje, allowed_mentions= discord.AllowedMentions(users=rol_asignado))

@bot.command()
async def offCumple(ctx):
    """
    Permite deshabilitar el control de cumpleaños.
    \n**Sintaxis**:
    >offCumple
    """
    global cumpleHabilitado
    if (id_owner_bot == ctx.message.author.id):
        cumpleHabilitado = False
        await ctx.send('Control de cumpleaños desactivado')
    else:
        await ctx.send('No tienes permisos para usar este comando')

@bot.command()
async def cumple(ctx, *args):
    """
    Permite guardar una fecha de cumpleaños para uno o mas usuarios.
    \n**Sintaxis**:
    >cumple <mencion> <fecha>               ->  >cumple @katherina 05/01
    >cumple <mencion1> <mencion2> <fecha>   ->  >cumple @katherina @usuario45 5/1
    *fecha*: en formato dd/mm, d/mm, d/m, dd/m.
    """
    if (default_channel):
        lfecha = []     #variable auxiliar para guardar la fecha de cumpleaños
        for i in args:
            if (i.startswith("<@!") != True):   #si no comienza, entonces es fecha y no mencion
                lfecha = i.strip().split('/')
        dfecha = datetime.date(2020 , int(lfecha[1]), int(lfecha[0]))   #verifico que la fecha tiene el formato correcto
        fecha = (dfecha.strftime('%d/%m/%Y'))[0:5]  #transformo la fecha en un string para luego trabajarla

        id_usuarios = []    #lista para almacenar los id de los usuarios mencionados
        for m in ctx.message.mentions:
            id_usuarios.append(m.id)
        dbirth = {} #diccionario estructura para almacenar usuario:fecha de cumpleaños
        fileExist = True    #bandera para saber si existe el archivo
        try:
            with open(birthday_path, 'r') as f:
                dbirth = json.load(f)
        except FileNotFoundError:
            print('El archivo no existe, se creara el archivo')
            fileExist = False
        if (fileExist):
            #si el archivo existe entonces entonces controlo si el usuario ya existe
            for idu in id_usuarios: #controlo por el ID de cada usuario
                if (matchUserWithDate(idu, fecha, dbirth) != True):
                    try:
                        #si no existe el conjunto (id, fecha), pero si existe la clave, entonces lo agrego.
                        dbirth[fecha].append(idu)   
                    except KeyError:
                        #si no existe la clave, entonces la creo y la agrego.
                        dbirth[fecha] = []
                        dbirth[fecha].append(idu)
        else:
            #si el archivo no existe entonces preparo para crearlo
            dbirth[fecha] = [] #creo la primera clave
            for idu in id_usuarios:
                dbirth[fecha].append(idu)   #agrego el primer valor
        with open(birthday_path, 'w') as f:
            json.dump(dbirth, f, indent=4)
        global cumpleHabilitado
        if(not cumpleHabilitado):   #si no esta habilitado, lo habilito e inicio el hilo de control
            cumpleHabilitado = True
            t = hiloCumples()
            t.start()
        await ctx.send("hecho")
    else:
        await ctx.send('Se debe setear un canal por defecto primero')

@bot.command()
async def cumples(ctx):
    """
    Lista de todas las fechas de cumpleaños guardadas.
    \n**Sintaxis**:
    >cumples
    """
    e = discord.Embed(title = 'Cumpleaños')
    if cumpleHabilitado:
        error = False
        try:
            birth = {}
            with open(birthday_path, 'r') as f:
                birth = json.load(f)
        except json.JSONDecodeError:
            error = True
        if (not error):
            message = ''
            for k in birth:
                message = message + k + ':'
                for v in k:
                    user = f'!<@{(discord.utils.get(ctx.guild.members, id=v)).name}>'
                    message = f'{message} {user}'
                message = message + '\n'
            e.description = message
        else:
            e.description = 'No hay cumpleaños'
    else:
        e.description = 'Función no habilitada'
    await ctx.send(embed= e)

@bot.command()
async def default(ctx):
    """
    Permite setear un nuevo default_channel para que el bot se comunique (Solo para administrador de bot).
    \n**Sintaxis**:
    >default
    """
    global default_channel
    if (id_owner_bot == ctx.message.author.id):
        default_channel = ctx.channel
        with open(config_path, 'r+') as f:
            config = json.load(f)
            config['default_channel'] = default_channel.name
            json.dump(config, f, indent=4)
        await ctx.send('Este canal sera utilizado para informar.')
    else:
        await ctx.send('No tienes permisos para utilizar este comando')

@bot.command()
async def owner(ctx):
    """
    Permite setear un nuevo Administrador del bot (Solo para administrador de bot).
    \n**Sintaxis**:
    >owner
    """
    global id_owner_bot
    if (id_owner_bot == ctx.message.author.id):
        id_owner_bot = (ctx.message.mentions[0]).id
        with open(config_path, 'r+') as f:
            config = json.load(f)
            config['id_owner_bot'] = id_owner_bot
            json.dump(config, f, indent=4)
        await ctx.send('Administrador del bot cambiado')
    else:
        await ctx.send('No tienes permisos para usar este comando')

"""
@bot.command()
async def encuesta(ctx):

    Permite publicar una encuesta.
    \nSintaxis:
    >encuesta #<texto_encuesta> | <opcion_1> # <opcion_n> | <nombre_rol_1> # <nombre_rol_2> 
    Ej.
    >encuesta #que prefieres? | azul # rojo # verde | kernel # superusuario
    
    menciones = ctx.message.raw_role_mentions
    respuesta = ''
    if (menciones):
        contenido = ctx.message.content.split('|')
        if (len(contenido) == 3):
            mensaje = (contenido[0].split('#',1))[1]
            opciones = contenido[1].split('#')
            roles = contenido[2].split['#']
        elif (len(contenido) > 3):
            respuesta = 'Argumentos excesivos'
        else:
            respuesta = 'Faltan argumentos'
    else:
        respuesta = 'NO hay menciones de roles'
"""    

@bot.command()
async def encuesta(ctx, opciones):
    """
    Permite realizar una encuesta. 
    **Paso1**: Escribir la encuesta en un mensaje normal y enviarlo al canal de texto.
    **Paso2**: Responder el mensaje con '>encuesta <numero_de_opciones>'.
    *numero_de_opciones*: numero de opciones que poseera la encuesta, puede ser de 1 a 10. 
    El numero_de_opciones se vera reflejado en el numero de reacciones disponibles en la encuesta.
    No se pueden realizar dos encuestas al mismo tiempo.
    Al considerar finalizada una encuesta se debe utilizar el comando '>finEncuesta'.
    \n**Sintaxis**:
    >encuesta <numero_de_opciones>  ->  >encuesta 5
    """
    global encuesta
    global reacciones_permitidas
    global id_autor_encuesta
    mensaje_referenciado = ctx.message.reference
    error = False
    if (encuesta):
        try:
            opciones = int(opciones)
        except ValueError:
            error = True
        if (opciones > 0 and opciones < 11):
            if (not error):
                if (mensaje_referenciado):
                    encuesta = await ctx.channel.fetch_message(mensaje_referenciado.message_id)
                    reacciones = encuesta.reactions
                    if (reacciones):
                        await encuesta.clear_reactions()
                    for i in range(opciones):
                        await encuesta.add_reaction(reacciones_encuesta[i])
                        reacciones_permitidas.append(reacciones_encuesta[i])
                    encuesta = encuesta.id
                    id_autor_encuesta = ctx.messsage.author.id
                else:
                    await ctx.send('Debes referenciar un mensaje con la encuesta. Para mas informacion usa >help <comando>')
        else:
            await ctx.send('numero_de_opciones ϵ [1, 10]')
    else:
        await ctx.send('Primero finaliza la encuesta anterior. Usa >help <comando> para mas información')

@bot.command()
async def finEncuesta(ctx):
    """
    Permite finalizar una encuesta.
    \n**Sintaxis**:
    >finEncuesta
    """
    global encuesta
    global reacciones_permitidas
    global reacciones_usuarios
    if (ctx.message.author.id == id_autor_encuesta or ctx.message.autohr.id == id_owner_bot):
        encuesta = None
        reacciones_permitidas = []
        reacciones_usuarios = []
    else:
        await ctx.send('No tienes permisos para finalizar esta encuesta')



#EVENTOS
@bot.event
async def on_member_join(member):
    """
    Asigna el rol "invitado" al usuario que acaba de unirse al servidor
    """
    # obtengo el rol invitado
    rol = discord.utils.get(member.guild.roles, name="invitado")
    await member.add_roles(rol)  # setea rol de invitado al recien llegado

@bot.event
async def on_guild_join(guild):
    """
    Mensaje del bot al unirse a un servidor
    """
    global default_channel
    global id_owner_bot
    global id_server
    default_channel = discord.utils.get(guild.text_channels, name = "general")
    id_owner_bot = guild.owner.id
    id_server = guild.id
    if (default_channel):
        config = {}
        config['id_server'] = id_server
        config['id_owner_bot'] = id_owner_bot
        config['default_channel'] = default_channel.name
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        await default_channel.send("Gracias por invitarme al servidor!!. Espero serte de utilidad")

@bot.event
async def on_ready():
    """
    Mensaje del bot al servidor al entrar en modo ON
    """
    command_names = []
    command_helps = []
    for c in bot.commands:
        command_names.append(c.name)
        command_helps.append(c.help)
    commands_dict = dict(zip(command_names, command_helps))
    with open(commands_path, 'w') as f:
        json.dump(commands_dict, f, indent=4)

    config = {}
    with open(config_path, 'r') as f:
        config = json.load(f)
    if (not os.path.exists(birthday_path)):
        with open(birthday_path, 'w') as f:
            pass
    if (not os.path.exists(calendar_path)):
        with open(calendar_path, 'w') as f:
            pass
    if (not os.path.exists(links_path)):
        with open(links_path, 'w') as f:
            pass
    if (not os.path.exists(works_path)):
        with open(works_path, 'w') as f:
            pass
    global default_channel
    global id_owner_bot
    global id_server
    server = discord.utils.get(bot.guilds, id = config['id_server'])
    id_server = server.id
    owner_bot = discord.utils.get(server.members, id = config['id_owner_bot'])
    if (owner_bot):
        id_owner_bot = owner_bot.id
    else:
        id_owner_bot = server.owner.id
    default_channel = discord.utils.get(server.text_channels, name = config['default_channel'])
    await default_channel.send('Estoy lista para recibir ordenes')

@bot.event
async def on_reaction_add(reaction, user):
    if (reaction.message.id == encuesta):
        mensaje = reaction.message
        if (not (reaction.emoji in reacciones_permitidas) and not (reaction.me)):    
            await mensaje.remove_reaction(reaction, user)
        elif (reaction.emoji in reacciones_permitidas):
            if (not (user.id in reacciones_usuarios)):
                reacciones_usuarios.append(user.id)
            else:
                await mensaje.remove_reaction(reaction, user)

@bot.event
async def on_reaction_remove(reaction, user):
    global reacciones_usuarios
    #codigo para dejar que cambien/saquen el voto
    if (reaction.message.id == encuesta):
        reacciones_usuarios.remove(user.id)

@bot.event
async def on_command_error(ctx, error):
    await ctx.send('Error en el comando. Usa >help <comando> para ver la sintaxis correcta')



bot.run(token)


