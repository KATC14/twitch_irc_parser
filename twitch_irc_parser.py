# Parses an IRC message and returns a JSON object with the message's 
# component parts (tags, source (nick and host), command, parameters). 
# Expects the caller to pass a single message. (Remember, the Twitch 
# IRC server may send one or more IRC messages in a single message.)

def msg_parser(message):
	parsedMessage = {# Contains the component parts.
		"tags": None,
		"source": None,
		"command": None,
		"message": None
	}

	# The start index. Increments as we parse the IRC message.
	idx = 0 

	# The raw components of the IRC message.
	rawTagsComponent = rawSourceComponent = rawCommandComponent = rawParametersComponent = None

	# If the message includes tags, get the tags component of the IRC message.
	if message[idx] == '@':# The message includes tags.
		endIdx = message.find(' ')
		rawTagsComponent = message[1:endIdx]
		idx = endIdx + 1 # Should now point to source colon (:).

	# Get the source component (nick and host) of the IRC message.
	# The idx should point to the source part otherwise, it's a PING command.
	if message[idx] == ':':
		idx += 1
		endIdx = message.find(' ', idx)
		rawSourceComponent = message[idx:endIdx]
		idx = endIdx + 1  # Should point to the command part of the message.

	# Get the command component of the IRC message.
	endIdx = message.find(':', idx)# Looking for the parameters part of the message.
	if -1 == endIdx:                # But not all messages include the parameters part.
		endIdx = len(message)

	rawCommandComponent = message[idx:endIdx].strip()

	# Get the parameters component of the IRC message.
	if endIdx != len(message):# Check if the IRC message contains a parameters component.
		idx = endIdx + 1            # Should point to the parameters part of the message.
		rawParametersComponent = message[idx:]

	# Parse the command component of the IRC message.
	parsedMessage['command'] = parseCommand(rawCommandComponent)

	# Only parse the rest of the components if it's a command
	# we care about we ignore some messages.
	if parsedMessage['command']:# Is None if it's a message we don't care about.
		if rawTagsComponent:# The IRC message contains tags.
			parsedMessage['tags'] = parseTags(rawTagsComponent)

		parsedMessage['source'] = parseSource(rawSourceComponent)

		parsedMessage['message'] = rawParametersComponent if rawParametersComponent != '-' else None
		if rawParametersComponent and rawParametersComponent[0] == '!':  
			# The user entered a bot command in the chat window.            
			parsedMessage['command'] = parseParameters(rawParametersComponent, parsedMessage['command'])

	return parsedMessage

# Parses the tags component of the IRC message.
def parseTags(tags):
	# badge-info=badges=broadcaster/1
	tagsToIgnore = {# List of tags to ignore.
		'client-nonce': None,
		'flags': None
	}

	dictParsedTags = {}# Holds the parsed list of tags. The key is the tag's name (e.g., color).
	parsedTags = tags.split(';')

	for tag in parsedTags:
		parsedTag = tag.split('=')  # Tags are key/value pairs.
		tagValue = None if parsedTag[1] == '' else parsedTag[1]

		match parsedTag[0]:# Switch on tag name
			case 'badges':
				# badges=staff/1,broadcaster/1,turbo/1
				if tagValue:
					dictt = {}# Holds the list of badge objects. The key is the badge's name (e.g., subscriber).
					badges = tagValue.split(',')
					for pair in badges:
						badgeParts = pair.split('/')
						dictt[badgeParts[0]] = badgeParts[1]
					dictParsedTags[parsedTag[0]] = dictt
				else:
					dictParsedTags[parsedTag[0]] = None
			case 'badge-info' | 'emotes':
				# emotes=25:0-4,12-16/1902:6-10
				if tagValue:
					dictEmotes = {}# Holds a list of emote objects. The key is the emote's ID.
					emotes = tagValue.split('/')
					for emote in emotes:
						emoteParts = emote.split(':', 1)

						textPositions = []  # The list of position objects that identify the location of the emote in the chat message.
						positions = emoteParts[1].split(',')
						for position in positions:
							positionParts = position.split('-')
							textPositions.append({
								"startPosition": positionParts[0],
								"endPosition": positionParts[1]    
							})

						dictEmotes[emoteParts[0]] = textPositions
					dictParsedTags[parsedTag[0]] = dictEmotes
				else:
					dictParsedTags[parsedTag[0]] = None
			case 'reply-parent-msg-body':
				dictParsedTags[parsedTag[0]] = tagValue.replace('\\s', ' ')
			case 'emote-sets':
				# emote-sets=0,33,50,237
				emoteSetIds = tagValue.split(',')  # Array of emote set IDs.
				dictParsedTags[parsedTag[0]] = emoteSetIds
			case _:
				# If the tag is in the list of tags to ignore, ignore
				# it otherwise, add it.
				if not tagsToIgnore.get(parsedTag[0]):
					dictParsedTags[parsedTag[0]] = tagValue

	return dictParsedTags

# Parses the command component of the IRC message.
def parseCommand(rawCommandComponent):
	parsedCommand = None
	commandParts = rawCommandComponent.split(' ')
	print(rawCommandComponent)

	match commandParts[0]:
		case 'JOIN' | 'PART' | 'NOTICE' | 'CLEARCHAT' | 'HOSTTARGET' | 'PRIVMSG':
			parsedCommand = {
				"command": commandParts[0],
				"channel": commandParts[1]
			}
		case 'PING':
			parsedCommand = {
				"command": commandParts[0]
			}
		case 'CAP':
			parsedCommand = {
				"command": rawCommandComponent,
				"isCapRequestEnabled": True if (commandParts[2] == 'ACK') else False,
				# The parameters part of the messages contains the 
				# enabled capabilities.
			}
		case 'GLOBALUSERSTATE':# Included only if you request the /commands capability But it has no meaning without also including the /tags capability.
			parsedCommand = {
				"command": commandParts[0]
			}
		# Included only if you request the /commands capability. But it has no meaning without also including the /tags capabilities.
		case 'USERSTATE' | 'ROOMSTATE' | 'USERNOTICE' | 'CLEARMSG':
			parsedCommand = {
				"command": commandParts[0],
				"channel": commandParts[1]
			}
		case 'RECONNECT':  
			print('The Twitch IRC server is about to terminate the connection for maintenance.')
			parsedCommand = {
				"command": commandParts[0]
			}
		case '421':
			print(f'Unsupported IRC command: {commandParts[2]}')
		case '001':  # Logged in (successfully authenticated).
			parsedCommand = {
				"command": commandParts[0],
				"channel": commandParts[1]
			}
			# Ignoring all other numeric messages.
			# 353 Tells you who else is in the chat room you're joining.
		case '002' | '003' | '004' | '353' | '366' | '372' | '375' | '376':
			parsedCommand = {
				"command": commandParts[0],
				"channel": commandParts[1]
			}
			#print(f'numeric message: {commandParts[0]}')
		case _:
			print(f'Unexpected command: {commandParts[0]}')

	return parsedCommand

# Parses the source (nick and host) components of the IRC message.
def parseSource(rawSourceComponent):
	if not rawSourceComponent:# Not all messages contain a source
		return None
	else:
		sourceParts = rawSourceComponent.split('!')
		return {
			"nick": sourceParts[0] if len(sourceParts) == 2 else None,
			"host": sourceParts[1] if len(sourceParts) == 2 else sourceParts[0]
		}

# Parsing the IRC parameters component if it contains a command (e.g., !dice).
def parseParameters(rawParametersComponent, command):
	idx = 0
	commandParts = rawParametersComponent[idx + 1:].strip() 
	paramsIdx = commandParts.find(' ')
	print(commandParts, paramsIdx)

	if -1 == paramsIdx: # no parameters
		command['botCommand'] = commandParts[0]
	else:
		command['botCommand'] = commandParts[:paramsIdx]
		command['botCommandParams'] = commandParts[paramsIdx:].strip()
		# TODO: remove extra spaces in parameters string

	return command