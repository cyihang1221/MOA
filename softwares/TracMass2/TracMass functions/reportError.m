function varargout=reportError
%by: Magnus Åberg
e=lasterror;
disp(e.message)
for i = 1:numel(e.stack)
   [p,n,foo] = fileparts(e.stack(i).file);
   str = [n,foo];
   if ~strcmpi(n,e.stack(i).name)
      str = [str, '>', e.stack(i).name];
   end
   fprintf(1,'<a href="error: %s, %i, 1">In %s Line:%i</a>\n',...
      e.stack(i).file,e.stack(i).line,str,e.stack(i).line)
end
if nargout
    varargout{1} = e;
end