function printStatus4(fmt,varargin)
%by: Magnus Åberg

persistent strs callers last_time callFiles
try
    do_print = false;

    stack = dbstack;
    if numel(stack) == 1,
        theCaller   = 'base';
        theCallFile = ' ';
    else
        theCallFile = stack(2).file;
        theCaller   = [stack(2).name];
    end

    % initialize
    if isempty(callers)
        callers   = {};
        callFiles = {};
        strs      = {};
        last_time = [];
    end
    
    nr=strmatch(theCaller,callers,'exact');
    oldCallers = callers;

    % first call from a caller
    if isempty(nr)
        callers{end+1}   = theCaller;
        callFiles{end+1} = theCallFile;
        strs{end+1}      = '';
        nr               = numel(callers);
        do_print         = true;
        last_time(nr)    = 0;
    end

    if cputime-last_time(nr)>3,  %print only if it was at least 3 secs since last print
        do_print = true;
    end

    % clear a caller
    if nargin==1,
        if strcmpi(fmt,'clear')
            theStr       = [strs{:}];
            fbackspace(1,theStr);
            callers(nr)  =[];
            callFiles(nr)=[];
            strs(nr)     =[];
        end
    end
    if do_print
        last_time(nr) = cputime;
        
        theStr = [strs{:}];
        fbackspace(1,theStr);
        theStr = [oldCallers{:}];
        fbackspace(1,theStr);
    end
    if nargin > 1 && do_print
        strs{nr} = sprintf(['> ', fmt],varargin{:});
    end

    if do_print
        for i = 1:numel(strs),
            if ~isempty(strs{i})
                fprintf(1,'<a href="matlab:edit(''%s'')"',callFiles{i});
                fprintf(1,'>%s</a>',callers{i});
                fprintf(1,'%s',strs{i});
            end
        end
        pause(0.001);
    end
catch
    reportError;
    keyboard
end
